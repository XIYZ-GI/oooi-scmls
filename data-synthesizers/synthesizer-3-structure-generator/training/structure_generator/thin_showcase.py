"""按厚度与专项分别选样，裁减后重验条件并发布本体。"""

import argparse
import json
from pathlib import Path

from ..serialization import write_json
from .extension_constraints import issue
from .reduction import reduce
from .showcase import publish
from .verification import verify_pulls


def eligible(row):
    c,m = row['coverage'],row['mechanisms']
    requested = row['requested_sampling']
    if m['functional_pushes']:
        return False
    if c['targets'] < requested['min_targets'] or c['density'] < requested['min_density']:
        return False
    return not issue(m,requested.get('options',{}))


def select(rows, per_cell=2):
    selected,seen,failures = [],set(),[]
    for depth in (2,3):
        for specialty in ('dense','large','extension'):
            pool = [r for r in rows if r['task']['depth']==depth and r['specialty']==specialty]
            def score(row):
                c,m = row['coverage'],row['mechanisms']
                return (c['density'],c['targets'],m['extended_input_pulls'],c['groups'])
            picked = 0
            for row in sorted(pool,key=score,reverse=True):
                if row['skeleton'] in seen:
                    continue
                candidate,reason = reduce(row)
                if reason:
                    failures.append(dict(record=row['id'],reason=reason))
                    continue
                if candidate['skeleton'] in seen or not eligible(candidate):
                    continue
                checks,reason = verify_pulls(candidate)
                if reason:
                    failures.append(dict(record=row['id'],reason=reason))
                    continue
                candidate['pull_ablation'] = checks
                selected.append(candidate)
                seen.update((row['skeleton'],candidate['skeleton']))
                picked += 1
                if picked == per_cell:
                    break
            if picked < per_cell:
                raise ValueError(f'{depth}格{specialty}只有{picked}条可展示独立骨架，需要{per_cell}条；未发布')
    return selected,failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources',type=Path,nargs='+',required=True,help='thin_suite的输出目录')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--per-cell',type=int,default=2)
    parser.add_argument('--tag',default='两格三格专项')
    parser.add_argument('--publish',action='store_true')
    parser.add_argument('--api',default='http://127.0.0.1:8010/api/datasets')
    args = parser.parse_args()
    if args.per_cell<1:
        parser.error('每个专项的展示数量必须为正')
    rows=[]
    for directory in args.sources:
        suite=json.loads((directory/'suite.json').read_text())
        if not suite['complete']:
            parser.error(f'{directory}的专项配额尚未完成')
        for cell in suite['cells']:
            for row in json.loads((Path(cell['output'])/'records.json').read_text()):
                rows.append({**row,'specialty':cell['profile']})
    write_json(args.output/'records.json',rows)
    selected,failures=select(rows,args.per_cell)
    write_json(args.output/'selected.json',selected)
    write_json(args.output/'selection-failures.json',failures)
    if args.publish:
        result=publish(selected,args.tag,args.api,args.output)
        print(json.dumps([dict(name=c['name'],id=c['scene']['id'],coverage=c['coverage'])
                          for c in result['cases']],ensure_ascii=False))
    else:
        print(json.dumps([r['coverage'] for r in selected],ensure_ascii=False))


if __name__ == '__main__':
    main()
