"""重放已有失败首候选，报告可直接观察的位移和事件。"""

from collections import Counter
import gzip
import json
from pathlib import Path

from ..evaluator import evaluate
from ..serialization import write_json


def main():
    root = Path('data/generation/stage4/diagnosis')
    root.mkdir(parents=True, exist_ok=True)
    source = json.loads(Path('data/generation/stage3-complete/failures/index.json').read_text())
    rows = []
    for record in source['records']:
        if record['split'] == 'thickness':
            continue
        proposal = record['candidates'][0]['proposal']
        result = evaluate(record['task'], proposal, capture=True)
        trace = result.pop('trace')
        with gzip.open(root/(record['task_id']+'.trace.json.gz'), 'wt') as handle:
            json.dump(trace, handle, ensure_ascii=False)
        first = {tuple(b['position'][a] for a in ('x', 'y', 'z')): b['id'] for b in trace[0]['snapshot']['blocks']}
        targets = []
        for target in record['task']['targets']:
            ids = [first[(target['x'], target['y'], target['z']+i)] for i in range(10)]
            tick, moved, complete = 0, 0, None
            for frame in trace[1:]:
                if frame['command']['type'] == 'step':
                    tick += frame['command']['ticks']
                actual = {b['id']: b['position'] for b in frame['snapshot']['blocks']}
                moved = sum(actual.get(bid) == dict(x=target['x'], y=target['y'], z=target['z']+i+1)
                            for i, bid in enumerate(ids))
                if moved == 10 and complete is None:
                    complete = tick
            targets.append({**target, 'completed_tick': complete, 'final_moved_blocks': moved})
        actual = {b['id']: b['position'] for b in trace[-1]['snapshot']['blocks']}
        stationary = [b for b in proposal['blocks'] if actual.get(first[tuple(b['position'][a] for a in ('x', 'y', 'z'))])
                      != {**b['position'], 'z': b['position']['z']+1}]
        events = [e for f in trace for e in f['snapshot']['events']]
        rows.append({'number': record['number'], 'task_id': record['task_id'], 'label': record['label'],
                     'evaluation': result, 'targets': targets, 'not_translated': stationary,
                     'events': events, 'event_counts': dict(Counter(e.get('kind', e.get('type', '未知')) for e in events))})
    write_json(root/'report.json', rows)
    for row in rows:
        print(json.dumps({'编号': row['number'], '完成刻': [t['completed_tick'] for t in row['targets']],
                          '未整体前进方块': len(row['not_translated']), '事件': row['event_counts']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
