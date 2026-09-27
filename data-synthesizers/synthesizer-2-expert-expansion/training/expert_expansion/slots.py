"""按明确供电邻接关系开放输出槽，单元实体数仍受十二块上限约束。"""

from copy import deepcopy
from itertools import product
import json
import random

from ..serialization import digest, write_json
from .config import ROOT
from .modules import AXES, xyz, orient


def output_slots(module):
    core={xyz(b['position']):b['block'] for b in module['core']}
    slots={xyz(p) for p in module['outputs']}
    for pos,b in core.items():
        if b['kind']!='observer':
            continue
        sign,axis=b['facing'].split('_');v=[0,0,0];v[AXES.index(axis)]=1 if sign=='positive' else -1
        receiver=tuple(p+d for p,d in zip(pos,v))
        if axis=='z' and sign=='positive' and receiver not in core:
            slots.add(receiver)
        if core.get(receiver,{}).get('kind') not in ('slime_block','honey_block','iron_block'):
            continue
        for i in range(3):
            for direction in (-1,1):
                p=list(receiver);p[i]+=direction;p=tuple(p)
                # 活塞前面不受电；朝正Z输出时不能从前侧强充能块取电。
                if i==2 and direction==-1:
                    continue
                if p not in core:
                    slots.add(p)
    ports={xyz(p['position']) for p in module['ports']}
    return [dict(zip(AXES,p)) for p in sorted(slots-ports-set(core))]


def canonical(module):
    keys=[]
    for swap,sx,sy,materials in product((False,True),(-1,1),(-1,1),(False,True)):
        m=orient(module,swap,sx,sy,materials)
        value=[sorted(m['core'],key=lambda b:xyz(b['position'])),
               sorted(m['ports'],key=lambda p:(xyz(p['position']),p['kind']))]
        keys.append(digest(value))
    return min(keys)


def strong_modules(seed=2026092202, count=300):
    rng=random.Random(seed);seen=set()
    for _ in range(count*50):
        hubs={(0,0)};glue=set()
        for _ in range(rng.choice((1,1,2))):
            x,y=rng.choice(sorted(hubs));dx,dy=rng.choice(((1,0),(-1,0),(0,1),(0,-1)))
            distance=rng.choice((2,3,4))
            nx,ny=x+distance*dx,y+distance*dy
            if (nx,ny) in hubs or (nx,ny) in glue:
                continue
            segment={(x+j*dx,y+j*dy) for j in range(1,distance)}
            if segment & hubs:
                continue
            hubs.add((nx,ny));glue.update(segment)
        if not glue or 2*len(hubs)+len(glue)>10:
            continue
        anchor=rng.choice(sorted(glue))
        blocks=[]
        for x,y in sorted(hubs):
            for z,kind in ((0,'observer'),(1,'slime_block')):
                blocks.append(dict(position=dict(x=x-anchor[0],y=y-anchor[1],z=z),block=dict(kind=kind,facing='positive_z')))
        for x,y in sorted(glue):
            blocks.append(dict(position=dict(x=x-anchor[0],y=y-anchor[1],z=0),block=dict(kind='slime_block',facing='positive_z')))
        m=dict(core=blocks,outputs=[],ports=[],input_kind='slime_block',sources=[dict(rule='多中心正交连接')])
        m['slots']=output_slots(m)
        # 可选择一个强充能侧口作为后继回拉接口；该口后方必须留给子单元。
        candidates=[p for p in m['slots'] if p['z']==1 and
                    (p['x'],p['y'],0) not in {xyz(b['position']) for b in blocks}]
        if candidates and rng.random()<.5 and len(blocks)<10:
            p=rng.choice(candidates)
            m['core'].append(dict(position=dict(p),block=dict(kind='sticky_piston',facing='negative_z')))
            m['ports']=[dict(position=dict(p),kind='pull')]
        m['slots']=output_slots(m)
        m['canonical']=canonical(m)
        if m['canonical'] in seen:
            continue
        seen.add(m['canonical']);m['id']=digest([m['core'],m['ports']])[:20]
        yield m
        if len(seen)>=count:
            break


def main():
    lib=json.loads((ROOT/'module-library.json').read_text())
    lib['modules']=[m for m in lib['modules'] if not m.get('procedural')]
    for m in lib['modules']:
        m['slots']=output_slots(m);m['canonical']=canonical(m)
    extra=list(strong_modules())
    for m in extra:
        m['procedural']=True
    lib['modules'].extend(extra)
    write_json(ROOT/'module-library.json',lib)
    print(json.dumps(dict(expert_modules=len(lib['modules'])-len(extra),procedural_modules=len(extra)),ensure_ascii=False))


if __name__=='__main__':
    main()
