"""分别构造两格、三格的密集、大尺寸与满位入口延伸专项。"""

import argparse
import json
from pathlib import Path
import subprocess
import sys

from ..serialization import write_json


def profiles(depth):
    placement = 'front' if depth == 2 else 'rear'
    common = ['--categories','推拉结合多时序','--depths',str(depth),
              '--min-extensions','1','--extension-placement',placement]
    dense = common if depth == 3 else ['--categories','推拉结合多时序','--depths','2',
                                           '--extension-share','.5']
    return {
        'dense':dense+['--min-targets','10' if depth == 2 else '13','--min-density','.4','--simulation-budget','96'],
        'large':common+['--min-targets','20','--min-density','.25','--min-long-side','10',
                        '--min-short-side','6','--simulation-budget','128'],
        'extension':common+['--min-targets','10','--min-density','.35',
                            '--min-saturated-extensions','1','--simulation-budget','96'],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--depths',nargs='+',type=int,choices=(2,3),default=[2,3])
    parser.add_argument('--profiles',nargs='+',choices=('dense','large','extension'),
                        default=['dense','large','extension'])
    parser.add_argument('--count',type=int,default=4,help='每种厚度的每个专项保存数量')
    parser.add_argument('--attempts',type=int,default=1600,help='每个专项的候选尝试上限')
    parser.add_argument('--workers',type=int,default=8)
    parser.add_argument('--seed',type=int,default=2026092510)
    args = parser.parse_args()
    if min(args.count,args.attempts,args.workers)<1:
        parser.error('数量、预算和进程数必须为正')
    total = len(args.depths)*len(args.profiles)
    all_completed = True
    summary = dict(complete=False,requested_cells=total,cells=[])
    for depth in args.depths:
        for name in args.profiles:
            output = args.output/f'{depth}-{name}'
            command = [sys.executable,'-m','training.structure_generator','--output',str(output),
                       '--count',str(args.count),'--attempts',str(args.attempts),
                       '--workers',str(args.workers),'--seed',str(args.seed),*profiles(depth)[name]]
            completed = subprocess.run(command,check=False)
            if completed.returncode not in (0,2):
                raise RuntimeError(f'{depth}格{name}执行异常，退出码{completed.returncode}')
            report = json.loads((output/'progress.json').read_text())
            summary['cells'].append(dict(depth=depth,profile=name,output=str(output),
                status=report['status'],attempts=report['attempts'],accepted=report['accepted'],
                conditions=report['identity'],coverage=report['coverage']))
            all_completed &= completed.returncode == 0
            summary['complete'] = all_completed and len(summary['cells']) == total
            write_json(args.output/'suite.json',summary)
    return 0 if summary['complete'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
