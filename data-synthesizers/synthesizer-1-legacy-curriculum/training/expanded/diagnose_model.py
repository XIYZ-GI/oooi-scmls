"""对少量拟合及开发需求生成原始候选，定位结构误差与失效表现。"""

import argparse
from collections import Counter
import json
from pathlib import Path

import torch

from ..data import read_examples
from ..evaluator import evaluate
from ..inference import generate, load_model
from ..serialization import digest, write_json


def main():
    parser = argparse.ArgumentParser(description='检查复杂课程的拟合与开发差距')
    parser.add_argument('--checkpoint', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    torch.set_num_threads(4)
    model, _ = load_model(args.checkpoint, 'cuda')
    root = Path('data/generation/stage4')
    records = [('fit', r) for r in read_examples(root/'fit-diagnostic.jsonl')]
    records += [('development', r) for r in read_examples(root/'development.jsonl') if r['family'] in ('path_varied', 'path_four')]
    rows = []
    for usage, record in records:
        torch.manual_seed(int(digest(['stage4_diagnose', record['task_id']])[:8], 16))
        proposals = generate(model, [record['task']], 'cuda') + generate(model, [record['task']]*7, 'cuda', .7)
        evaluations = [evaluate(record['task'], p) for p in proposals]
        reference = {tuple(b['position'][a] for a in ('x', 'y', 'z')): b['block'] for b in record['proposal']['blocks']}
        actual = {tuple(b['position'][a] for a in ('x', 'y', 'z')): b['block'] for b in proposals[0]['blocks']}
        differences = [{'position': p, 'reference': reference.get(p), 'generated': actual.get(p)}
                       for p in sorted(reference.keys() | actual.keys()) if reference.get(p) != actual.get(p)]
        proof = evaluate(record['task'], proposals[0], capture=True)
        events = [e for f in proof.get('trace', []) for e in f['snapshot']['events'] if 'blocked' in e['kind']]
        row = {'usage': usage, 'record': record, 'proposals': proposals, 'evaluations': evaluations,
               'greedy_differences': differences, 'blocked_events': events,
               'accepted': any(e['accepted'] for e in evaluations)}
        rows.append(row)
        print(json.dumps({'用途': usage, '任务': record['task_id'], '成功': row['accepted'],
                          '首候选与参考不同位置': len(differences), '阻挡': [e['message'] for e in events]}, ensure_ascii=False), flush=True)
    write_json(args.output, rows)


if __name__ == '__main__':
    main()
