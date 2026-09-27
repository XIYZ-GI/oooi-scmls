"""课程准备后按实际骨架覆盖冻结分层用途，训练前执行一次。"""

from collections import Counter, defaultdict
from copy import deepcopy
import json
from pathlib import Path

from ..compact_round2.prepare import write_rows
from ..compact_round2.rules import geometry
from ..data import read_examples
from ..serialization import digest, write_json


def main():
    root = Path('data/generation/stage4')
    if (root/'frozen.json').exists():
        raise ValueError('最终用途已冻结，不能覆盖')
    original = read_examples(root/'examples.jsonl')
    paths = [r for r in original if r['family'] in ('path_varied', 'path_four')]
    for family in ('path_varied', 'path_four'):
        groups = sorted({r['group'] for r in paths if r['family'] == family}, key=lambda g: digest(['stage4_frozen', g]))
        dev, held = (4, 5) if family == 'path_varied' else (12, 24)
        assignment = {g: 'development' if i < dev else 'heldout' if i < dev+held else 'fit' for i, g in enumerate(groups)}
        for row in paths:
            if row['family'] == family:
                row['usage'] = assignment[row['group']]
                row['split'] = {'fit': 'train', 'development': 'validation', 'heldout': 'test'}[row['usage']]
    paths += read_examples(root/'dense.jsonl')
    held_geo = {geometry(r['task']) for r in paths if r['usage'] == 'heldout'}
    dev_geo = {geometry(r['task']) for r in paths if r['usage'] == 'development'} - held_geo
    paths = [r for r in paths if r['usage'] == 'heldout' or
             (r['usage'] == 'development' and geometry(r['task']) not in held_geo) or
             (r['usage'] == 'fit' and geometry(r['task']) not in held_geo | dev_geo)]
    old = [r for r in original if r['family'] == 'retention' and geometry(r['task']) not in held_geo | dev_geo]
    records = [*old, *paths]
    slack = []
    for row in records:
        if row['usage'] != 'fit' or row['task']['depth'] >= 4:
            continue
        for depth in range(row['task']['depth']+1, 5):
            copy = deepcopy(row);copy['task']['depth'] = depth;copy['family'] = 'slack'
            copy.update(id=digest([copy['task'], copy['proposal']])[:24], task_id=digest(copy['task'])[:24])
            slack.append(copy)
    records += slack
    development = [r for r in read_examples(root/'development.jsonl') if r['family'] in ('retention', 'slack')]
    heldout = []
    for usage, dest in [('development', development), ('heldout', heldout)]:
        for family in ('path_varied', 'path_four', 'dense'):
            rows = sorted([r for r in paths if r['usage'] == usage and r['family'] == family], key=lambda r: digest(['choose4', r['id']]))
            group_counts = Counter()
            selected = []
            limit = 4 if usage == 'development' else 10 if family == 'path_varied' else 16
            for row in rows:
                if group_counts[row['group']] >= (2 if family == 'path_varied' and usage == 'heldout' else 1):
                    continue
                selected.append(row);group_counts[row['group']] += 1
                if len(selected) >= limit:
                    break
            dest.extend(selected)
    write_rows(root/'examples.jsonl', records)
    write_rows(root/'development.jsonl', development)
    write_rows(root/'heldout.jsonl', heldout)
    plan = json.loads((root/'experiment-plan.json').read_text())
    plan.update(family_sampling={'retention': .30, 'slack': .20, 'path_varied': .15, 'path_four': .25, 'dense': .10})
    write_json(root/'experiment-plan.json', plan)
    goals = json.loads((root/'stage-goals.json').read_text())
    goals.update(dense_minimum_rate=.75, frame_7x5_target15_required=True, dense_maximum_depth=4,
                 dense_scope='七乘五截面同一平面目标，四格厚度，两组时序的三个机械分组完整构造。六格对照不计达标。')
    write_json(root/'stage-goals.json', goals)
    write_json(root/'frozen.json', {'counts': dict(Counter(r['usage']+'/'+r['family'] for r in records)),
        'heldout_counts': dict(Counter(r['family'] for r in heldout)),
        'development_counts': dict(Counter(r['family'] for r in development)),
        'heldout_topologies': {f: len({r['group'] for r in heldout if r['family'] == f}) for f in ('path_varied', 'path_four', 'dense')},
        'data_digest': digest((root/'examples.jsonl').read_text()),
        'stage_goals_digest': digest((root/'stage-goals.json').read_text()),
        'note': '准备阶段按实际可用骨架分层固定；此时未运行任何第四阶段训练或模型评估。'})
    print((root/'frozen.json').read_text())


if __name__ == '__main__':
    main()
