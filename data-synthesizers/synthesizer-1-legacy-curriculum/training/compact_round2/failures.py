"""直接发布最终评估已有失败候选，不调用模型或模拟器。"""

import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen

from ..serialization import digest, write_json
from .failure_report import render_report


def main():
    parser = argparse.ArgumentParser(description='发布已评估的失败结构和十负载装配')
    parser.add_argument('--runs', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--sources', default='data/generation/stage3/examples.jsonl')
    parser.add_argument('--report', default='docs/stage3-failures.md')
    parser.add_argument('--api', default='http://127.0.0.1:8010/api')
    args = parser.parse_args()
    runs, output = Path(args.runs), Path(args.output)
    checkpoint = json.loads((runs/'frozen-checkpoints.json').read_text())['current']
    sources = {}
    for line in Path(args.sources).read_text().splitlines():
        row = json.loads(line)
        if row.get('source_name'):
            sources.setdefault(row['group'], set()).add(row['source_name'])
    records, scenes = [], []
    for split, split_label in [('heldout', '新几何'), ('regression', '历史能力检查'), ('thickness', '厚度对照')]:
        for line in (runs/f'current-{split}'/'results.jsonl').read_text().splitlines():
            row = json.loads(line)
            if row['accepted']:
                continue
            task = row['task']
            label = split_label
            if row['family'] == 'expert_compact':
                label = '人工样本需求·'+ '、'.join(sorted(sources.get(row['group'], {'来源未记录'})))
            record = {k: row[k] for k in ('task_id', 'task', 'family', 'group')}
            record.update(number=len(records)+1, split=split, label=label, candidates=[])
            seen = {}
            for number, (proposal, evaluation) in enumerate(zip(row['proposals'], row['evaluations'], strict=True), 1):
                fingerprint = digest({'push': proposal['push'], 'blocks': sorted(proposal['blocks'], key=lambda b: tuple(b['position'][a] for a in ('x', 'y', 'z')))})
                if fingerprint in seen:
                    seen[fingerprint]['original_candidates'].append(number)
                    continue
                if evaluation.get('duplicate') or not evaluation.get('reason'):
                    raise ValueError('不同候选缺少实际模拟判定，不能发布为已评估失败')
                short = '时序不符' if '顺序' in evaluation['reason'] else '未完成负载'
                candidate = {'number': number, 'original_candidates': [number], 'proposal': proposal,
                             'evaluation': evaluation, 'reason_short': short, 'scenes': []}
                seen[fingerprint] = candidate
                loads = [{'position': dict(x=t['x'], y=t['y'], z=t['z']+i),
                          'block': {'kind': 'iron_block', 'facing': 'positive_z'}}
                         for t in task['targets'] for i in range(task['load_blocks'])]
                actuator = {'position': {**proposal['push'], 'z': proposal['push']['z']-1},
                            'block': {'kind': 'piston', 'facing': 'positive_z'}}
                base = (f"阶段3失败{record['number']:02d}·{label}·{len(task['targets'])}目标"
                        f"{len({t['order'] for t in task['targets']})}时序·限厚{task['depth']}·候选{number}·{short}")
                for suffix, blocks in [('本体', proposal['blocks']), ('十负载装配', [*proposal['blocks'], *loads, actuator])]:
                    if len({tuple(b['position'][a] for a in ('x', 'y', 'z')) for b in blocks}) != len(blocks):
                        raise ValueError(f'{base}存在重叠，不能覆盖原方块发布')
                    scene = {'id': digest(['stage3_failed', row['task_id'], number, suffix, blocks]),
                             'name': base+'·'+suffix, 'blocks': blocks}
                    candidate['scenes'].append({'source_id': scene['id'], 'name': scene['name']})
                    scenes.append(scene)
                record['candidates'].append(candidate)
            records.append(record)
    write_json(output/'scenes.json', {'items': scenes})
    request = Request(args.api.rstrip('/')+'/datasets/scenes/migrate',
                      data=json.dumps({'items': scenes}, ensure_ascii=False).encode(),
                      headers={'Content-Type': 'application/json'}, method='POST')
    with urlopen(request, timeout=60) as response:
        saved = json.load(response)
    if len(saved['items']) != len(scenes):
        raise ValueError('服务器返回的结构数量与提交不符')
    published = iter(saved['items'])
    for record in records:
        for candidate in record['candidates']:
            for scene in candidate['scenes']:
                stored = next(published)
                scene.update({k: stored[k] for k in ('id', 'name', 'revision')})
    write_json(output/'index.json', {'checkpoint_sha256': checkpoint, 'records': records})
    Path(args.report).write_text(render_report(records, checkpoint))
    print(json.dumps({'失败需求记录': len(records), '不同候选': sum(len(r['candidates']) for r in records),
                      '服务器结构': len(scenes), '新增结构': saved['added']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
