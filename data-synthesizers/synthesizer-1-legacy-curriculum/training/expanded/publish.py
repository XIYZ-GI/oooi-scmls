"""把第四阶段同一模型的有效结构及失败代表保存到服务器结构库。"""

import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen

from ..data import read_examples
from ..serialization import digest, write_json


def main():
    parser = argparse.ArgumentParser(description='发布第四阶段模型的原始结构及十负载装配')
    parser.add_argument('--runs', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    runs, output = Path(args.runs), Path(args.output)
    result = json.loads((runs/'result.json').read_text())
    splits = ['heldout', 'retention', 'thickness']
    if (runs/'current-fresh/results.jsonl').exists():
        splits.append('fresh')
    records = [r for name in splits for r in read_examples(runs/('current-'+name)/'results.jsonl')]
    chosen = []
    for label, predicate in [
        ('十五目标四格', lambda r: r['family'] == 'dense' and len(r['task']['targets']) == 15),
        ('四时序两格拉驱', lambda r: r['family'] == 'path_four' and r['actual_depth'] == 2
         and max(t['order'] for t in r['task']['targets']) == 4 and r['mechanisms']['nonempty_pull_operations'] > 0),
        ('五时序两格拉驱', lambda r: r['family'] == 'path_four' and r['actual_depth'] == 2
         and max(t['order'] for t in r['task']['targets']) == 5 and r['mechanisms']['nonempty_pull_operations'] > 0),
        ('新路径三时序', lambda r: r['family'] == 'path_varied'),
        ('五目标允许四格', lambda r: r['family'] == 'strong_compact_depth4'),
    ]:
        options = [r for r in records if r['accepted'] and predicate(r)]
        if options:
            row = max(options, key=lambda r: (len(r['task']['targets']), r['task_id']))
            chosen.append(('阶段4模型·'+label, row, row['first_success_candidate']-1))
    unique_failures = {}
    for row in records:
        if not row['accepted']:
            unique_failures.setdefault(row['task_id'], row)
    for i, row in enumerate(unique_failures.values(), 1):
        chosen.append((f"阶段4未通过{i:02d}·{len(row['task']['targets'])}目标·限厚{row['task']['depth']}·首候选", row, 0))
    scenes, index = [], []
    for label, row, number in chosen:
        proposal, task = row['proposals'][number], row['task']
        loads = [{'position': dict(x=t['x'], y=t['y'], z=t['z']+i),
                  'block': {'kind': 'iron_block', 'facing': 'positive_z'}} for t in task['targets'] for i in range(10)]
        actuator = {'position': {**proposal['push'], 'z': proposal['push']['z']-1},
                    'block': {'kind': 'piston', 'facing': 'positive_z'}}
        entry = {'name': label, 'task_id': row['task_id'], 'task': task, 'proposal': proposal,
                 'evaluation': row['evaluations'][number], 'candidate_number': number+1, 'scenes': []}
        for suffix, blocks in [('本体', proposal['blocks']), ('十负载装配', [*proposal['blocks'], *loads, actuator])]:
            if len({tuple(b['position'][a] for a in ('x', 'y', 'z')) for b in blocks}) != len(blocks):
                entry['assembly_note'] = '装配坐标冲突，保留本体和原始失败判定，未覆盖原方块。'
                continue
            scene = {'id': digest(['stage4', result['checkpoint_sha256'], label, suffix, blocks]),
                     'name': label+'·'+suffix, 'blocks': blocks}
            scenes.append(scene)
            entry['scenes'].append({'name': scene['name'], 'source_id': scene['id']})
        index.append(entry)
    write_json(output/'scenes.json', {'items': scenes})
    request = Request('http://127.0.0.1:8010/api/datasets/scenes/migrate',
                      data=json.dumps({'items': scenes}, ensure_ascii=False).encode(),
                      headers={'Content-Type': 'application/json'}, method='POST')
    with urlopen(request, timeout=60) as response:
        saved = json.load(response)
    stored = iter(saved['items'])
    for entry in index:
        for scene in entry['scenes']:
            scene.update({k: v for k, v in next(stored).items() if k in ('id', 'name', 'revision')})
    write_json(output/'showcase.json', {'checkpoint_sha256': result['checkpoint_sha256'], 'exhibits': index})
    print(json.dumps({'成功代表': len(chosen)-len(unique_failures), '失败代表': len(unique_failures),
                      '服务器结构': len(scenes), '新增': saved['added']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
