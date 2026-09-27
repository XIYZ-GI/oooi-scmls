"""冻结第五阶段需求、来源隔离和初始权重，不构造任何结构答案。"""

import json
from pathlib import Path
import random
import shutil
import sqlite3

from ..serialization import digest, write_json
from .config import PLAN
from .demands import geometry, random_task


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, ensure_ascii=False)+'\n' for row in rows))


def record(task, family):
    return {'task': task, 'task_id': digest(task)[:24], 'geometry': geometry(task), 'family': family}


def main():
    root = Path('data/generation/stage5')
    if (root/'experiment-plan.json').exists():
        raise ValueError('第五阶段需求已冻结，禁止覆盖')
    root.mkdir(parents=True, exist_ok=True)
    experts, regression = [], []
    source = Path('data/generation/stage1/expert-snapshot.json')
    for row in json.loads(source.read_text()):
        task = {key: row[key] for key in ('width', 'height', 'depth')}
        task.update(targets=[{k: t[k] for k in ('x', 'y', 'z', 'order')} for t in row['reference']['targets']],
                    max_ticks=row['request']['max_ticks'], rounds=3, load_blocks=10)
        task['targets'].sort(key=lambda t: (t['x'], t['y']))
        item = {**record(task, 'expert'), 'source_id': row['id'], 'name': row['name'], 'original_split': row['split']}
        (experts if row['split'] == 'train' else regression).append(item)
    web = {}
    with sqlite3.connect('file:data/generation/web/generation.sqlite3?mode=ro', uri=True) as db:
        for (raw,) in db.execute('SELECT task FROM jobs WHERE deleted=0 ORDER BY created_at'):
            task = json.loads(raw)
            task['targets'].sort(key=lambda t: (t['x'], t['y']))
            item = record(task, 'web')
            web[item['task_id']] = item
    seen = {geometry(r['task']) for r in [*experts, *regression, *web.values()]}
    for path in Path('data/generation').glob('*/examples.jsonl'):
        for line in path.read_text().splitlines():
            row = json.loads(line)
            if row.get('task', {}).get('targets'):
                seen.add(geometry(row['task']))
    rng = random.Random(PLAN['seed']+700)
    splits = {}
    for split, count in [('development', 48), ('heldout', 96)]:
        rows = []
        while len(rows) < count:
            # 评估重心为2～12目标，仍保留更多目标需求，记录未知可解性。
            task = random_task(rng)
            key = geometry(task)
            if key in seen:
                continue
            seen.add(key)
            rows.append(record(task, 'simultaneous' if max(t['order'] for t in task['targets']) == 1 else 'multigroup'))
        splits[split] = rows
    excluded = {r['geometry'] for rows in splits.values() for r in rows}
    excluded.update(r['geometry'] for r in regression)
    excluded.update(r['geometry'] for r in web.values())
    experts = [r for r in experts if r['geometry'] not in excluded]
    write_rows(root/'experts.jsonl', experts)
    write_rows(root/'expert-regression.jsonl', regression)
    write_rows(root/'web-regression.jsonl', list(web.values()))
    for split, rows in splits.items():
        write_rows(root/(split+'.jsonl'), rows)
    write_json(root/'excluded-geometries.json', sorted(excluded))
    shutil.copyfile('data/generation/stage4/accelerated-artifacts/runs/stage4-accelerated/best.pt', root/'initial.pt')
    write_json(root/'experiment-plan.json', PLAN)
    write_json(root/'manifest.json', {'expert_demands': len(experts), 'expert_regression': len(regression),
        'web_regression': len(web), 'development': 48, 'heldout': 96, 'excluded_geometries': len(excluded),
        'files': {p.name: digest(p.read_text()) for p in root.glob('*.jsonl')},
        'expert_source_digest': digest(source.read_text()),
        'note': '训练只读取专家需求，不读取结构答案；保留原专家来源划分。随机需求不保证可解。网页需求为已知失败回归集合。'})
    print((root/'manifest.json').read_text())


if __name__ == '__main__':
    main()
