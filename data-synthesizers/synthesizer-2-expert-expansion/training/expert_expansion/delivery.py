"""保存全部18项需求的三轮轨迹和构造证据，发布到服务器结构库。"""

import argparse
import gzip
import hashlib
import json
from urllib.request import Request, urlopen

from ..compact.mechanisms import analyze
from ..evaluator import evaluate
from ..serialization import digest, write_json
from .config import ROOT
from .gate import require_all, require_case
from .required import refresh


def sorted_targets(task):
    return sorted((t['x'], t['y'], t['z'], t['order']) for t in task['targets'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--names',nargs='+',help='只发布指定已通过项，不放行整体扩量门槛')
    args = parser.parse_args()
    all_experts = json.loads((ROOT/'experts.json').read_text())
    if args.names:
        if not set(args.names) <= {e['name'] for e in all_experts}:
            raise ValueError('存在未知的专家需求名称')
        experts = [e for e in all_experts if e['name'] in args.names]
    else:
        experts = require_all()
    reports, scenes = [], []
    report = json.loads((ROOT/'coverage-report.json').read_text())
    for expert in experts:
        path = ROOT/'required'/(expert['id']+'.json')
        result = json.loads(path.read_text())
        require_case(expert,result)
        if not result['accepted']:
            raise ValueError(expert['name']+'未通过，不能发布成功结构')
        solution = result['solution'];task = solution['task'];proposal = solution['proposal']
        assert sorted_targets(task) == sorted_targets(expert['task'])
        assert all(task[k] == expert['task'][k] for k in ('width','height','depth'))
        proof = evaluate(task, proposal, capture=True, foundation=True, feedback=True, require_activation=False)
        if not proof['accepted']:
            raise ValueError(expert['name']+'装配结果复核不通过')
        trace = proof.pop('trace')
        trace_path = ROOT/'required'/(expert['id']+'.trace.json.gz')
        with gzip.open(trace_path, 'wt') as stream:
            json.dump(dict(task=task, proposal=proposal, evaluation=proof, trace=trace), stream, ensure_ascii=False)
        zs = [b['position']['z'] for b in proposal['blocks']]
        key = lambda b: (b['position']['x'],b['position']['y'],b['position']['z'],b['block']['kind'],b['block']['facing'])
        evidence = dict(name=expert['name'],id=expert['id'],accepted=True,task=task,
            assembly_method=solution['assembly_method'],
            actual_depth=max(zs)-min(zs)+1,blocks=len(proposal['blocks']),push=proposal['push'],
            same_layout_as_expert=sorted(map(key,proposal['blocks']))==sorted(map(key,expert['proposal']['blocks'])),
            evaluation=proof,mechanisms=analyze(trace),trace=str(trace_path),
            trace_sha256=hashlib.sha256(trace_path.read_bytes()).hexdigest(),
            solution_sha256=digest([task,proposal]),connections=solution['modules'])
        reports.append(evidence)
        write_json(ROOT/'required'/(expert['id']+'.proof.json'),evidence)
        write_json(ROOT/'coverage'/(expert['id']+'.json'),result)
        report['cases']=[({k:v for k,v in result.items() if k not in ('solution','failures')} if r['id']==expert['id'] else r)
                         for r in report['cases']]
        prefix='课程构造·'+expert['name']+'同目标·统一求解'
        scenes.append(dict(id=digest(['expert-expansion',expert['id'],'body']),name=prefix+'·本体',blocks=proposal['blocks']))
        loads=[dict(position=dict(x=t['x'],y=t['y'],z=t['z']+i),block=dict(kind='iron_block',facing='positive_z'))
               for t in task['targets'] for i in range(10)]
        actuator=dict(position={**proposal['push'],'z':proposal['push']['z']-1},block=dict(kind='piston',facing='positive_z'))
        scenes.append(dict(id=digest(['expert-expansion',expert['id'],'loads']),name=prefix+'·十负载',
                           blocks=[*proposal['blocks'],*loads,actuator]))
    report['passed']=sum(r['accepted'] for r in report['cases'])
    report = refresh(all_experts)
    current_proofs = []
    for expert in all_experts:
        proof_path = ROOT/'required'/(expert['id']+'.proof.json')
        result_path = ROOT/'required'/(expert['id']+'.json')
        if not proof_path.exists() or not result_path.exists():
            continue
        saved_proof = json.loads(proof_path.read_text())
        saved_result = json.loads(result_path.read_text())
        try:
            require_case(expert,saved_result)
        except ValueError:
            continue
        saved_solution = saved_result['solution']
        if (saved_proof.get('assembly_method') == 'constraint_solver_v2'
                and saved_proof['solution_sha256'] == digest([saved_solution['task'],saved_solution['proposal']])
                and saved_proof['evaluation']['engine_version'] == saved_solution['evaluation']['engine_version']):
            current_proofs.append(saved_proof)
    write_json(ROOT/'required-proof.json',dict(accepted=len(current_proofs)==18,required=18,cases=current_proofs,
        scope='从专家提取的局部机制及接口构造；专家样本已用于研究。此结果是构造器能力验收，不是神经网络生成或未见专家泛化。'))
    request=Request('http://127.0.0.1:8010/api/datasets/scenes/migrate',
                    data=json.dumps(dict(items=scenes)).encode(),headers={'Content-Type':'application/json'},method='POST')
    with urlopen(request,timeout=60) as response:
        saved=json.load(response)
    published_path = ROOT/'published.json'
    previous = json.loads(published_path.read_text()).get('scenes',[]) if published_path.exists() else []
    merged = {r['id']:r for r in previous}
    merged.update({r['id']:{k:r[k] for k in ('id','name','revision')} for r in saved['items']})
    write_json(published_path,dict(scenes=list(merged.values())))
    print(json.dumps(dict(covered=report['passed'],published=len(saved['items']),
                         required=[dict(name=r['name'],depth=r['actual_depth'],same_layout=r['same_layout_as_expert']) for r in reports]),ensure_ascii=False))


if __name__=='__main__':
    main()
