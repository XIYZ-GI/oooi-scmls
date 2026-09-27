"""仅给专家需求，用运行单元接口约束装配；不读取该题的成品或装配配方。"""

from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from itertools import product
import json
import time

from ..evaluator import evaluate
from ..serialization import digest, write_json
from .config import ROOT
from .modules import AXES, instantiate, orient, xyz
from .transport import transport_valid


def solve(task, modules, seconds=90, limit=100):
    started=time.monotonic();w,h,d=task['width'],task['height'],task['depth']
    grid=[(x,y,z) for x in range(w) for y in range(h) for z in range(-d-1,-1)]
    index={p:i for i,p in enumerate(grid)}
    target={xyz(t):i for i,t in enumerate(task['targets'])};orders=[t['order'] for t in task['targets']]
    loads={(t['x'],t['y'],t['z']+i) for t in task['targets'] for i in range(10)}
    variants={}
    # 专家提取的局部单元可任意旋转；运行时不读取专家身份或连接配方。
    for original in modules:
        if original.get('procedural'):
            continue
        for swap,sx,sy in product((False,True),(-1,1),(-1,1)):
            m=orient(original,swap,sx,sy)
            key=digest([m['core'],m.get('slots',m['outputs']),m['ports']])
            variants[key]=m
    options=defaultdict(list)
    for m in variants.values():
        for a in grid:
            anchor=dict(zip(AXES,a))
            positions=[tuple(b['position'][k]+anchor[k] for k in AXES) for b in m['core']]
            if any(p not in index or p in loads for p in positions):
                continue
            selections=defaultdict(list)
            for p in m.get('slots',m['outputs']):
                t=(p['x']+a[0],p['y']+a[1],p['z']+a[2]+2)
                if t in target:
                    selections[orders[target[t]]].append(p)
            choices=list(selections.values())
            original={xyz(p) for p in m['outputs']}
            choices.extend([[p for p in chosen if xyz(p) in original] for chosen in list(choices)])
            if m['ports']:
                choices.append([])
            used=set()
            for chosen in choices:
                signature=tuple(sorted(xyz(p) for p in chosen))
                if signature in used or (not chosen and not m['ports']):
                    continue
                used.add(signature)
                if len(m['core'])+len(chosen)>12:
                    continue
                covered=[target[(p['x']+a[0],p['y']+a[1],p['z']+a[2]+2)] for p in chosen]
                blocks,_,ports=instantiate(m,anchor,chosen)
                positions=[xyz(b['position']) for b in blocks]
                if any(p not in index or p in loads for p in positions):
                    continue
                children=[({**p['position'],'z':p['position']['z']+(-1 if p['kind']=='pull' else 2)},
                           8 if p['kind']=='pull' else 4,xyz(p['position'])) for p in ports]
                if any(xyz(p) not in index for p,_,_ in children):
                    continue
                node=dict(blocks=blocks,mask=sum(1<<index[p] for p in positions),covered=covered,
                          targets=sum(1<<i for i in covered),children=children,module=m['id'],anchor=anchor)
                options[a].append(node)
    for nodes in options.values():
        nodes.sort(key=lambda n:(-len(n['covered']),len(n['blocks']),-len(n['children'])))
    roots=[n for nodes in options.values() for n in nodes]
    roots.sort(key=lambda n:(-len(n['covered']),len(n['blocks']),-len(n['children'])))
    all_targets=(1<<len(target))-1;examined=0;steps=0;answer=None;attempted=set()

    def walk(frontier, occupied, covered, stamps, placed, push):
        nonlocal steps,examined,answer
        steps+=1
        if time.monotonic()-started>seconds or examined>=limit:
            return True
        if not frontier:
            if covered!=all_targets:
                return False
            blocks=[b for n in placed for b in n['blocks']]
            proposal=dict(blocks=blocks,push=push);key=digest(proposal)
            if key in attempted:
                return False
            attempted.add(key);examined+=1
            value=evaluate(task,proposal,foundation=True)
            if value['accepted']:
                answer=dict(task=task,proposal=proposal,evaluation=value,
                            modules=[dict(id=n['module'],anchor=n['anchor']) for n in placed])
                return True
            return False
        if len(placed)>=12:
            return False
        anchor,tick,driver=frontier[0]
        candidates=options.get(xyz(anchor),[]) if anchor is not None else roots
        for node in candidates:
            if node['mask']&occupied or node['targets']&covered:
                continue
            updated=dict(stamps)
            good=True
            for i in node['covered']:
                order=orders[i];stamp=tick+6
                if any((o==order and v!=stamp) or (o<order and v>=stamp) or (o>order and v<=stamp)
                       for o,v in updated.items()):
                    good=False;break
                updated[order]=stamp
            if not good:
                continue
            a=node['anchor']
            moving={**node,'tick':tick,'parent':None if driver is None else 0,
                    'driver':driver or (a['x'],a['y'],a['z']-1)}
            if not transport_valid([*placed,moving]):
                continue
            queue=[*frontier[1:],*[(p,tick+delay,actuator) for p,delay,actuator in node['children']]]
            # 没有任何单元能接入的接口立即剪枝。
            if any(xyz(p) not in options for p,_,_ in queue):
                continue
            if walk(queue,occupied|node['mask'],covered|node['targets'],updated,[*placed,moving],push or node['anchor']):
                return True
        return False

    walk([(None,0,None)],0,0,{},[],None)
    return dict(accepted=answer is not None,solution=answer,seconds=time.monotonic()-started,
                assembly_states=steps,complete_proposals=examined,placed_options=len(roots),
                note='时间和候选上限内未找到不代表无解；仅从目标需求及局部单元库装配，没有读取本题成品配方')


def solve_one(payload):
    expert,modules=payload
    path=ROOT/'coverage'/(expert['id']+'.json')
    if path.exists():
        previous=json.loads(path.read_text())
        if previous['accepted']:
            return previous
    result=solve(expert['task'],modules)
    result.update(name=expert['name'],id=expert['id'])
    write_json(ROOT/'coverage'/(expert['id']+'.json'),result)
    print(json.dumps({k:v for k,v in result.items() if k!='solution'},ensure_ascii=False),flush=True)
    return result


def main():
    experts=json.loads((ROOT/'experts.json').read_text())
    modules=json.loads((ROOT/'module-library.json').read_text())['modules']
    with ProcessPoolExecutor(max_workers=4) as pool:
        rows=list(pool.map(solve_one,[(e,modules) for e in experts]))
    write_json(ROOT/'legacy-dfs-report.json',dict(required=18,total=len(rows),passed=sum(r['accepted'] for r in rows),
        cases=[{k:v for k,v in r.items() if k!='solution'} for r in rows],
        scope='历史DFS探索记录，不作为正式18项构造验收入口'))


if __name__=='__main__':
    main()
