"""在新课程冻结题上按固定候选预算评估旧架构模型，结果按题保存可续跑。"""

import argparse
import collections
import hashlib
import json
import multiprocessing
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import time

import torch

from ...accelerated.symmetry import PROTOCOL, generate_symmetric
from ...evaluator import evaluate
from ...inference import load_model
from ...serialization import digest, write_json
from .stage4_dataset import DEFAULT_EXPORT


def verify(row):
    """单候选完整判定：十负载、连续三轮、整线平移与设计禁忌。"""
    return evaluate(row['task'], row['proposal'], foundation=True, feedback=True)


def band(case):
    """按目标数量、时序组数、允许厚度和截面面积分档，便于比较能力边界。"""
    task = case['task']
    count, groups = len(task['targets']), len({t['order'] for t in task['targets']})
    targets = '2至5目标' if count <= 5 else '6至12目标' if count <= 12 else '13至32目标'
    area = task['width']*task['height']
    size = '小截面' if area <= 25 else '中截面' if area <= 64 else '大截面'
    return '%s/%s/%d时序/%d格' % (targets, size, groups, task['depth'])


def summarize(cases, rows):
    by_band = collections.defaultdict(lambda: dict(tasks=0, passed=0, candidates=0, accepted=0))
    cohorts = collections.defaultdict(lambda: dict(tasks=0, passed=0, candidates=0, accepted=0))
    for case, row in zip(cases, rows):
        key, cohort = band(case), case['cohort']
        accepted = sum(bool(m['accepted']) for m in row['metrics'])
        for table in (by_band[key], cohorts[cohort]):
            table['tasks'] += 1
            table['passed'] += int(accepted > 0)
            table['candidates'] += len(row['metrics'])
            table['accepted'] += accepted
    return dict(overall=dict(tasks=len(rows), passed=sum(any(m['accepted'] for m in r['metrics']) for r in rows),
                             candidates=sum(len(r['metrics']) for r in rows),
                             accepted=sum(sum(bool(m['accepted']) for m in r['metrics']) for r in rows)),
                by_band=dict(by_band), by_cohort=dict(cohorts))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', required=True)
    parser.add_argument('--model-id', required=True)
    parser.add_argument('--tasks', type=Path, default=DEFAULT_EXPORT / 'eval-tasks.json')
    parser.add_argument('--output', type=Path, default=DEFAULT_EXPORT / 'evaluation')
    parser.add_argument('--candidates', type=int, default=8)
    parser.add_argument('--workers', type=int, default=0)
    parser.add_argument('--limit', type=int, default=0, help='只评估前若干题，用于快速检查流程')
    parser.add_argument('--seed', type=int, default=20260923)
    args = parser.parse_args()
    for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[key] = '1'
    torch.set_num_threads(1)
    cases = json.loads(args.tasks.read_text())['cases']
    if args.limit:
        cases = cases[:args.limit]
    output = args.output/args.model_id
    output.mkdir(parents=True, exist_ok=True)
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    workers = args.workers or (14 if device == 'cuda' else min(6, max(1, (os.cpu_count() or 2)-2)))
    checkpoint = Path(args.checkpoint)
    plan = dict(model_id=args.model_id, checkpoint=str(checkpoint),
                checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                tasks_sha256=digest(cases), candidates=args.candidates, protocol=PROTOCOL,
                temperature=0.0, device=device, workers=workers, seed=args.seed)
    write_json(output/'plan.json', plan)
    model, _ = load_model(checkpoint, device)
    started, rows = time.monotonic(), []
    with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context('spawn')) as pool:
        for index, case in enumerate(cases):
            path = output/(case['id']+'.json')
            if path.exists():
                rows.append(json.loads(path.read_text()))
                continue
            seed = int(hashlib.sha256(('%d:%s' % (args.seed, case['id'])).encode()).hexdigest()[:8], 16)
            proposals = generate_symmetric(model, [dict(task=case['task'])], device, args.candidates, seed)[0]
            evaluations = list(pool.map(verify, [dict(task=case['task'], proposal=p) for p in proposals]))
            row = dict(id=case['id'], cohort=case['cohort'], coverage=case['coverage'],
                       actual_depth=case['actual_depth'], task=case['task'], seed=seed,
                       band=band(case), metrics=[dict(accepted=value['accepted'], reason=value['reason'],
                                                      translation=value.get('foundation', {}).get('translation'),
                                                      rounds=len(value.get('rounds', []))) for value in evaluations],
                       candidates=[dict(proposal=p, accepted=value['accepted']) for p, value in zip(proposals, evaluations)])
            write_json(path, row)
            rows.append(row)
            if (index+1) % 5 == 0:
                print(json.dumps(dict(model=args.model_id, evaluated=index+1, total=len(cases),
                                      passed=sum(any(m['accepted'] for m in r['metrics']) for r in rows),
                                      seconds=round(time.monotonic()-started)), ensure_ascii=False), flush=True)
    report = summarize(cases, rows)
    report.update(plan=plan, seconds=time.monotonic()-started)
    write_json(output/'report.json', report)
    print(json.dumps(report['overall'], ensure_ascii=False), flush=True)
    for key, value in sorted(report['by_band'].items()):
        print('%-34s %3d/%3d 需求' % (key, value['passed'], value['tasks']), flush=True)


if __name__ == '__main__':
    main()
