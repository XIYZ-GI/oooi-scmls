"""按打标器顺序冻结专家需求，记录每个搬运操作及供电机制。"""

from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import gzip
import json
from pathlib import Path
import sqlite3
from urllib.request import urlopen

from ..compact.mechanisms import analyze
from ..evaluator import evaluate
from ..serialization import digest, write_json
from .config import ROOT


def experts():
    source = Path('data/generation/stage1/expert-snapshot.json')
    raw = json.loads(source.read_text())
    rows = raw if isinstance(raw, list) else raw['examples']
    with sqlite3.connect('file:data/mcscai.sqlite3?mode=ro', uri=True) as db:
        order = {r[0]: i for i, r in enumerate(db.execute(
            "SELECT id FROM documents WHERE kind='samples' AND deleted=0 ORDER BY position,updated_at"))}
    result = []
    for r in sorted(rows, key=lambda r: order.get(r['id'], 999)):
        result.append(dict(id=r['id'], name=r['name'], original_split=r['split'],
            task=dict(width=r['width'], height=r['height'], depth=r['depth'],
                      targets=[{k: t[k] for k in ('x', 'y', 'z', 'order')} for t in r['reference']['targets']],
                      max_ticks=r['request']['max_ticks'], rounds=3, load_blocks=10),
            proposal=dict(blocks=r['request']['blocks'], push=r['request']['push_point'])))
    with urlopen('http://127.0.0.1:8010/api/datasets/samples/7829c0ab-a94a-4c47-b012-c1f87e40ac9d') as response:
        sample = json.load(response)
    if sample['timing']['status'] != 'success':
        raise ValueError('移动线21尚无有效目标时序')
    result.append(dict(id=sample['id'], name=sample['name'], original_split='mechanism_research',
        source_revision=sample['revision'], original_max_ticks=sample['timing']['maxTicks'],
        task=dict(width=sample['normalized']['width'], height=sample['normalized']['height'], depth=6,
                  targets=[{k:t[k] for k in ('x','y','z','order')} for t in sample['timing']['targets']],
                  max_ticks=200, rounds=3, load_blocks=10),
        proposal=dict(blocks=[dict(position=b['position'], block=dict(kind=b['kind'],
                              facing=b['facing'] if b['kind'] in ('piston','sticky_piston','observer') else 'positive_z'))
                              for b in sample['normalized']['blocks']], push=sample['pushPoint'])))
    return result


def inspect(row):
    result = evaluate(row['task'], row['proposal'], capture=True, foundation=True, require_activation=False)
    trace = result.pop('trace')
    if not trace:
        raise ValueError(row['name']+'不能生成审计轨迹：'+result['reason'])
    path = ROOT/'traces'/(row['id']+'.json.gz')
    with gzip.open(path, 'wt') as handle:
        json.dump(trace, handle, ensure_ascii=False)
    initial = {tuple(b['position'][a] for a in ('x', 'y', 'z')): b for b in trace[0]['snapshot']['blocks']}
    members = {initial[tuple(b['position'][a] for a in ('x', 'y', 'z'))]['id']: b for b in row['proposal']['blocks']}
    operations = {}
    for frame in trace:
        s = frame['snapshot']
        if s['tick'] > row['task']['max_ticks']:
            break
        for m in s['motions']:
            key = (m['piston_id'], m['kind'], m['started_at'])
            if key in operations:
                continue
            moved = [b['block_id'] for b in m['blocks'] if b['block_id'] in members]
            if moved:
                operations[key] = dict(kind=m['kind'], start=m['started_at'], end=m['completes_at'],
                    piston=members.get(m['piston_id'], {'external': True}),
                    blocks=[members[i] for i in moved], block_ids=moved)
    return dict(**row, evaluation=result, mechanisms=analyze(trace), operations=list(operations.values()),
                kinds=dict(Counter(b['block']['kind'] for b in row['proposal']['blocks'])),
                trace=str(path), fingerprint=digest([row['task'], row['proposal']]))


def main():
    (ROOT/'traces').mkdir(parents=True, exist_ok=True)
    rows = experts()
    write_json(ROOT/'experts.json', rows)
    with ProcessPoolExecutor(max_workers=6) as pool:
        reports = list(pool.map(inspect, rows))
    write_json(ROOT/'expert-audit.json', reports)
    for r in reports:
        print(json.dumps(dict(name=r['name'], accepted=r['evaluation']['accepted'],
            reason=r['evaluation']['reason'], operations=[dict(kind=o['kind'], start=o['start'],
            piston=o['piston'].get('position'), count=len(o['blocks'])) for o in r['operations']]), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
