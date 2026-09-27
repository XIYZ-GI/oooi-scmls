"""将阶段验收模型的代表结构与来源证据保存到服务器。"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
from urllib.request import Request, urlopen

from ..serialization import digest, write_json


def main():
    parser = argparse.ArgumentParser(description='发布同一检查点的阶段结构成果')
    parser.add_argument('--runs', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    runs, output = Path(args.runs), Path(args.output)
    result = json.loads((runs/'result.json').read_text())
    if not result['stage3_complete']:
        raise ValueError('阶段条件尚未全部满足，不能发布为完成成果')
    frozen = json.loads((runs/'frozen-checkpoints.json').read_text())['current']
    if hashlib.sha256((runs/'best.pt').read_bytes()).hexdigest() != frozen:
        raise ValueError('模型摘要与已验收检查点不一致')
    rows = result['successful']+result['regression_successful']
    selected = []
    for family, count, label in (
        ('mixed_two', 6, '6目标两时序混材拉驱'),
        ('mixed_three', 8, '8目标三时序混材拉驱'),
        ('strong_wide', 11, '11目标四格同推'),
        ('strong_compact', 5, '5目标两格强充能'),
        ('expert_compact', 5, '交错目标强充能'),
    ):
        choices = [r for r in rows if r['family'] == family and len(r['task']['targets']) == count
                   and (family == 'expert_compact' or r['mechanism_valid'])]
        if choices:
            selected.append((label, min(choices, key=lambda r: r['task_id'])))
    output.mkdir(parents=True, exist_ok=True)
    scenes, exhibits = [], []
    for label, row in selected:
        task, proposal = row['task'], row['proposal']
        write_json(output/('阶段3成果·'+label+'.task.json'), task)
        if row['family'] == 'mixed_three':
            write_json(output.parent/'example.task.json', task)
        loads = [{'position': dict(x=t['x'], y=t['y'], z=t['z']+i),
                  'block': {'kind': 'iron_block', 'facing': 'positive_z'}} for t in task['targets'] for i in range(10)]
        piston = {'position': {**proposal['push'], 'z': proposal['push']['z']-1},
                  'block': {'kind': 'piston', 'facing': 'positive_z'}}
        for suffix, blocks in (('本体', proposal['blocks']), ('十负载装配', [*proposal['blocks'], *loads, piston])):
            name = '阶段3成果·'+label+'·'+suffix
            scene = {'id': digest(['stage3_complete', name, blocks]), 'name': name, 'blocks': blocks}
            scenes.append(scene)
            write_json(output/(name+'.scene.json'), scene)
        exhibits.append({'name': '阶段3成果·'+label, **row})
    request = Request('http://127.0.0.1:8010/api/datasets/scenes/migrate',
        data=json.dumps({'items': scenes}, ensure_ascii=False).encode(),
        headers={'Content-Type': 'application/json'}, method='POST')
    with urlopen(request, timeout=60) as response:
        saved = json.load(response)
    shutil.copyfile(runs/'best.pt', output.parent/'model.pt')
    write_json(output/'showcase.json', {'checkpoint_sha256': frozen, 'exhibits': exhibits,
        'published': [{k: r[k] for k in ('name', 'id', 'revision')} for r in saved['items']]})
    print(json.dumps({'场景': [r['name'] for r in saved['items']], '模型': str(output.parent/'model.pt')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
