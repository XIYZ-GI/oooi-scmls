"""冻结模型后，以每任务固定随机流生成并保存完整运行证据。"""

import argparse
from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import time

import torch

from ..compact.mechanisms import analyze
from ..data import read_examples
from ..evaluator import evaluate
from ..inference import generate, load_model
from ..serialization import digest, write_json


def main():
    parser = argparse.ArgumentParser(description='第四阶段同任务预算完整生成评估')
    parser.add_argument('--checkpoint', required=True)
    parser.add_argument('--data', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--seed', type=int, default=41)
    parser.add_argument('--candidates', type=int, default=8)
    args = parser.parse_args()
    output = Path(args.output)
    if (output/'report.json').exists() or (output/'results.jsonl').exists():
        raise ValueError('已有评估，不覆盖')
    output.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(4)
    torch.backends.cuda.matmul.allow_tf32 = True
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model, _ = load_model(args.checkpoint, device)
    started = time.monotonic()
    groups = defaultdict(lambda: {'tasks': 0, 'successes': 0, 'greedy': 0})
    details = []
    records = read_examples(args.data)
    write_json(output/'tasks.json', [{k: r[k] for k in ('task_id', 'task', 'family', 'group')} for r in records])
    with (output/'results.jsonl').open('w') as handle:
        for record in records:
            task = record['task']
            torch.manual_seed(int(digest(['stage4_evaluation', args.seed, record['task_id']])[:8], 16))
            proposals = generate(model, [task], device)
            if args.candidates > 1:
                proposals += generate(model, [task]*(args.candidates-1), device, .7)
            evaluations, seen, first = [], set(), None
            for i, proposal in enumerate(proposals):
                key = digest(proposal)
                if key in seen:
                    evaluations.append({'accepted': False, 'duplicate': True})
                    continue
                seen.add(key)
                result = evaluate(task, proposal)
                evaluations.append(result)
                if result['accepted'] and first is None:
                    first = i
            row = {k: record[k] for k in ('task_id', 'task', 'family', 'group')}
            row.update(accepted=first is not None, first_success_candidate=first+1 if first is not None else None,
                       greedy_success=evaluations[0]['accepted'], proposals=proposals, evaluations=evaluations)
            if first is not None:
                proof = evaluate(task, proposals[first], capture=True)
                if not proof['accepted']:
                    raise RuntimeError('成功候选重放不一致')
                with gzip.open(output/(record['task_id']+'.trace.json.gz'), 'wt') as trace:
                    json.dump(proof, trace, ensure_ascii=False)
                row['mechanisms'] = analyze(proof['trace'])
                zs = [b['position']['z'] for b in proposals[first]['blocks']]
                row['actual_depth'] = max(zs)-min(zs)+1
            group = groups[record['family']]
            group['tasks'] += 1
            group['successes'] += row['accepted']
            group['greedy'] += row['greedy_success']
            details.append(row)
            handle.write(json.dumps(row, ensure_ascii=False)+'\n'); handle.flush()
            print(json.dumps({'需求': len(details), '成功': sum(r['accepted'] for r in details),
                              '族': record['family']}, ensure_ascii=False), flush=True)
    write_json(output/'report.json', {'checkpoint_sha256': hashlib.sha256(Path(args.checkpoint).read_bytes()).hexdigest(),
        'parameters': model.parameter_report(), 'tasks': len(details), 'successes': sum(r['accepted'] for r in details),
        'greedy_successes': sum(r['greedy_success'] for r in details), 'families': dict(groups),
        'seed': args.seed, 'candidate_budget': args.candidates, 'seconds': time.monotonic()-started,
        'candidate_simulator_runs': sum(e.get('simulator_started', False) for r in details for e in r['evaluations']),
        'data_sha256': hashlib.sha256(Path(args.data).read_bytes()).hexdigest(),
        'scope': '新连接骨架、历史能力和厚度对照分开保存；来源范围由冻结数据清单说明。'})


if __name__ == '__main__':
    main()
