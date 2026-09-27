"""全部18项专家需求为扩量前必过项，旧成功结构按当前引擎复核。"""

import argparse
import json

import mcscai_engine

from ..evaluator import evaluate
from ..serialization import write_json
from ..serialization import digest
from .config import ROOT
from .constraint_solver import solve
from .gate import REQUIRED_NAMES, require_case


def refresh(experts):
    rows = []
    for e in experts:
        path = ROOT/'required'/(e['id']+'.json')
        r = json.loads(path.read_text()) if path.exists() else dict(accepted=False)
        reason = (r.get('solution') or {}).get('evaluation',{}).get('reason',r.get('status','尚未求解'))
        try:
            require_case(e,r)
            accepted = True
        except ValueError as error:
            accepted = False
            reason = reason or str(error)
        rows.append(dict(name=e['name'],id=e['id'],accepted=accepted,reason=reason))
    report = dict(passed=sum(r['accepted'] for r in rows),required=18,total=len(rows),cases=rows,
                  engine_version=mcscai_engine.__version__,scope='专家机制构造覆盖，不是神经网络生成或未见需求泛化')
    write_json(ROOT/'required-report.json',report)
    write_json(ROOT/'coverage-report.json',report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cached-only',action='store_true',help='只复核已有成功结构')
    parser.add_argument('--force',action='store_true',help='忽略已有结果，全部使用同一组合求解器重算')
    parser.add_argument('--names',nargs='*',help='只求解指定名称，验收总门槛仍为18项')
    parser.add_argument('--seconds',type=int,default=900)
    args = parser.parse_args()
    experts = json.loads((ROOT/'experts.json').read_text())
    if {e['name'] for e in experts} != REQUIRED_NAMES or len(experts) != 18:
        raise ValueError('专家需求集合必须恰好包含约定的18项')
    library = json.loads((ROOT/'module-library.json').read_text())
    for e in experts:
        if args.names and e['name'] not in args.names:
            continue
        print(e['name'], flush=True)
        path=ROOT/'required'/(e['id']+'.json')
        previous = None
        for candidate in (path,ROOT/'coverage'/(e['id']+'.json')):
            if not candidate.exists():
                continue
            row = json.loads(candidate.read_text())
            if not args.force and row['accepted'] and row.get('solution',{}).get('modules') \
                    and row.get('solution',{}).get('assembly_method') == 'constraint_solver_v2' \
                    and digest(row['solution']['task']) == digest(e['task']):
                previous = row
                break
        if previous:
            value = previous['solution']['evaluation']
            if value.get('engine_version') != mcscai_engine.__version__:
                value = evaluate(e['task'],previous['solution']['proposal'],foundation=True,require_activation=False)
            previous['solution']['evaluation'] = value
            previous['accepted'] = value['accepted']
            write_json(path,previous)
            if value['accepted']:
                continue
        if args.cached_only:
            continue
        result = solve(e['task'], library['modules'],seconds=args.seconds,limit=300)
        if result.get('solution'):
            result['solution']['assembly_method'] = 'constraint_solver_v2'
        result.update(name=e['name'], id=e['id'])
        write_json(path, result)
        refresh(experts)
    print(json.dumps(refresh(experts),ensure_ascii=False),flush=True)


if __name__ == '__main__':
    main()
