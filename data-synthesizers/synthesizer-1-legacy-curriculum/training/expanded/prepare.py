"""按连接骨架划分第四阶段路径课程，再确认完整运行。"""

from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from itertools import product
import json
from pathlib import Path
import random
import time

from ..compact.transforms import transform
from ..compact_round2.rules import geometry
from ..compact_round2.prepare import write_rows
from ..data import read_examples
from ..prepare import simulate_example
from ..serialization import digest, write_json
from ..templates import geometry_key
from .paths import pull_path

ROOT = Path('data/generation/stage4')


def prototypes(multiplier=1, seed=20260930):
    rng = random.Random(seed)
    seen = set()
    for count in (2, 3, 4, 5):
        wanted = (100 if count == 2 else 300)*multiplier
        emitted = 0
        for attempt in range(16000):
            hubs = [(1, 1)]
            for _ in range(count-1):
                dx, dy = rng.choice(((1, 0), (-1, 0), (0, 1), (0, -1)))
                length = rng.choice((2, 3, 4))
                hubs.append((hubs[-1][0]+dx*length, hubs[-1][1]+dy*length))
            if len(set(hubs)) != count:
                continue
            sides = [rng.choice((-1, 1)) for _ in range(count-1)]
            try:
                row = pull_path(hubs, sides)
            except ValueError:
                continue
            task = row['task']
            if task['width']*task['height'] > 90 or max(task['width'], task['height']) > 15:
                continue
            key = digest(row['proposal'])
            if key in seen:
                continue
            seen.add(key)
            skeleton = digest(geometry_key([(x, y, 0, i+1) for i, (x, y) in enumerate(hubs)]))
            row['group'] = 'path-'+skeleton
            bucket = int(digest(['stage4_topology', skeleton])[:8], 16) % 10
            row['usage'] = 'development' if bucket == 0 else 'heldout' if bucket == 1 else 'fit'
            row['family'] = 'path_four' if count >= 4 else 'path_varied'
            row['split'] = {'fit': 'train', 'development': 'validation', 'heldout': 'test'}[row['usage']]
            yield row
            emitted += 1
            if emitted >= wanted:
                break


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    if (ROOT/'manifest.json').exists():
        raise ValueError('第四阶段课程已冻结，不覆盖')
    started = time.monotonic()
    candidates = list(prototypes())
    write_json(ROOT/'allocation.json', [{'group': r['group'], 'usage': r['usage'], 'topology': r['topology']} for r in candidates])
    valid, rejected = [], []
    with ProcessPoolExecutor(max_workers=6) as pool:
        for i, row in enumerate(pool.map(simulate_example, candidates, chunksize=4)):
            (valid if row['evaluation']['accepted'] else rejected).append(row)
            if (i+1) % 100 == 0:
                print(json.dumps({'已确认构造': i+1, '有效': len(valid)}, ensure_ascii=False), flush=True)
    write_rows(ROOT/'prototypes.jsonl', valid)
    write_rows(ROOT/'rejected.jsonl', rejected)
    # 输出组合改变后重新执行物理确认；镜像等变换也执行，允许空间扩展不改变世界。
    variants = []
    for row in valid:
        variants.append(transform(row))
        variants.append(transform(row, swap=True, sx=-1, materials=True))
        rng = random.Random(int(digest(row['proposal'])[:12], 16))
        for trial in range(3):
            chosen = []
            for order in sorted({t['order'] for t in row['task']['targets']}):
                options = [t for t in row['task']['targets'] if t['order'] == order]
                chosen += rng.sample(options, rng.randint(1, len(options)))
            chosen = sorted(chosen, key=lambda t: (t['x'], t['y']))
            copy = deepcopy(row)
            remove = {(t['x'], t['y'], -2) for t in row['task']['targets'] if t not in chosen}
            copy['task']['targets'] = chosen
            copy['proposal']['blocks'] = [b for b in copy['proposal']['blocks'] if
                tuple(b['position'][a] for a in ('x', 'y', 'z')) not in remove]
            variants.append(transform(copy, swap=bool(trial % 2), sx=-1 if trial == 2 else 1))
    variants = list({digest([r['task'], r['proposal']]): r for r in variants}.values())
    accepted = []
    with ProcessPoolExecutor(max_workers=6) as pool:
        for row in pool.map(simulate_example, variants, chunksize=4):
            if row['evaluation']['accepted']:
                accepted.append(row)
    # 以目标几何为第二层隔离，避免不同路径恰好给出同一任务造成泄漏。
    held_geometries = {geometry(r['task']) for r in accepted if r['usage'] == 'heldout'}
    dev_geometries = {geometry(r['task']) for r in accepted if r['usage'] == 'development'} - held_geometries
    accepted = [r for r in accepted if
                (r['usage'] == 'heldout') or
                (r['usage'] == 'development' and geometry(r['task']) not in held_geometries) or
                (r['usage'] == 'fit' and geometry(r['task']) not in held_geometries | dev_geometries)]
    old = [deepcopy(r) for r in read_examples('data/generation/stage3-balanced/examples.jsonl') if r['usage'] == 'fit']
    old = [r for r in old if geometry(r['task']) not in held_geometries | dev_geometries]
    for row in old:
        row['family'] = 'retention'
    fit = [r for r in accepted if r['usage'] == 'fit']
    slack = []
    for row in [*fit, *old]:
        if row['task']['depth'] >= 4:
            continue
        for depth in range(row['task']['depth']+1, 5):
            copy = deepcopy(row)
            copy['task']['depth'] = depth
            copy.update(id=digest([copy['task'], copy['proposal']])[:24], task_id=digest(copy['task'])[:24])
            copy['family'] = 'slack'
            slack.append(copy)
    development, heldout = [], []
    for usage, dest, per_family in [('development', development, 6), ('heldout', heldout, 16)]:
        for family in ('path_varied', 'path_four'):
            rows = sorted([r for r in accepted if r['usage'] == usage and r['family'] == family], key=lambda r: digest(['select4', r['id']]))
            selected, seen = [], set()
            # 每个骨架至多一个需求，数量覆盖由固定排序选择。
            for row in rows:
                if row['group'] not in seen:
                    selected.append(row); seen.add(row['group'])
                if len(selected) == per_family:
                    break
            dest.extend(selected)
    old_development = read_examples('data/generation/stage3-balanced/development.jsonl')
    by_family = defaultdict(list)
    for row in old_development:
        by_family[row['family']].append(row)
    for family, rows in by_family.items():
        for row in sorted(rows, key=lambda r: r['task_id'])[:2]:
            row = deepcopy(row); row['family'] = 'retention'; row['split'] = 'validation'
            development.append(row)
            if row['task']['depth'] < 4:
                row = deepcopy(row);row['task']['depth'] = 4;row['task_id'] = digest(row['task'])[:24];row['family'] = 'slack'
                development.append(row)
    records = [*old, *accepted, *slack]
    write_rows(ROOT/'examples.jsonl', records)
    write_rows(ROOT/'development.jsonl', development)
    write_rows(ROOT/'heldout.jsonl', heldout)
    plan = dict(seed=20260930, steps=18000, batch_size=12, learning_rate=0.00008,
                validation_interval=3000, selection_candidates=4, max_training_seconds=7200,
                initial_checkpoint='runs/stage3-balanced/best.pt', depth_slack_max=0,
                family_sampling={'retention': .35, 'slack': .20, 'path_varied': .20, 'path_four': .25})
    write_json(ROOT/'experiment-plan.json', plan)
    write_json(ROOT/'stage-goals.json', {'new_family_minimum_rate': .75, 'minimum_heldout_tasks_per_family': 8,
        'four_timing_success': True, 'large_target_minimum': 12, 'target15_required': True,
        'retention_minimum_successes': 129, 'retention_tasks': 136,
        'thickness_minimum_successes': 10, 'thickness_tasks': 12,
        'scope': '按路径骨架隔离的新组合，不等于跨未知红石原理。保留人工来源单列，7×5十五目标必须披露覆盖状态。'})
    write_json(ROOT/'manifest.json', {'prototypes_attempted': len(candidates), 'prototypes_accepted': len(valid),
        'verified_variants': len(accepted), 'counts': dict(Counter(r['usage']+'/'+r['family'] for r in records)),
        'heldout': dict(Counter(r['family'] for r in heldout)), 'development': dict(Counter(r['family'] for r in development)),
        'maximum_targets': max(len(r['task']['targets']) for r in accepted),
        'groups': {u: sorted({r['group'] for r in accepted if r['usage'] == u}) for u in ('fit', 'development', 'heldout')},
        'seconds': time.monotonic()-started, 'data_digest': digest((ROOT/'examples.jsonl').read_text())})
    print((ROOT/'manifest.json').read_text(), flush=True)


if __name__ == '__main__':
    main()
