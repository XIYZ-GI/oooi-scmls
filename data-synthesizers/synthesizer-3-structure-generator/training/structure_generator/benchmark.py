"""用相同种子和候选预算对比原始布局搜索与物理回退搜索。"""

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import time

from ..serialization import digest, write_json
from .config import CATEGORIES
from .worker import generate


def measure(jobs, workers):
    started = time.monotonic()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(generate,jobs))
    seconds = time.monotonic()-started
    rows = [v['row'] for v in results if 'row' in v]
    unique = {r['canonical'] for r in rows}
    summary = dict(attempts=len(jobs),accepted=len(rows),unique=len(unique),seconds=round(seconds,3),
                   unique_per_second=round(len(unique)/seconds,3),
                   reasons=dict(Counter(v['reason'] or '通过' for v in results)),
                   categories={c:dict(attempts=sum(j[2]==c for j in jobs),
                                      accepted=sum(r['family']==c for r in rows)) for c in CATEGORIES},
                   targets_13_plus=sum(r['coverage']['targets']>=13 for r in rows),
                   targets_20_plus=sum(r['coverage']['targets']>=20 for r in rows),
                   density_40_plus=sum(r['coverage']['density']>=.4 for r in rows),
                   density_50_plus=sum(r['coverage']['density']>=.5 for r in rows),
                   input_extensions=sum(r['mechanisms']['extended_input_pulls']>0 for r in rows))
    return summary,results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--per-category',type=int,default=120)
    parser.add_argument('--workers',type=int,default=8)
    parser.add_argument('--seed',type=int,default=2026092401)
    parser.add_argument('--simulation-budget',type=int,default=64)
    args = parser.parse_args()
    if min(args.per_category,args.workers,args.simulation_budget)<1:
        parser.error('候选数、进程数和物理预筛预算必须为正')
    report = dict(seed=args.seed,per_category=args.per_category,
                  source_digest=digest({p.name:p.read_text() for p in Path(__file__).parent.glob('*.py')}))
    for mode in ('legacy','guided'):
        jobs = [(i,args.seed,c,4,True,3,0.,dict(search=mode=='guided',
                 simulation_budget=args.simulation_budget)) for c in CATEGORIES for i in range(args.per_category)]
        summary,results = measure(jobs,args.workers)
        report[mode] = summary
        write_json(args.output/f'{mode}-results.json',results)
        print(mode,summary,flush=True)
    write_json(args.output/'report.json',report)


if __name__ == '__main__':
    main()
