"""从搬运轨迹记录机械连接、跨单元供电、分叉同步和材料隔离。"""

from collections import Counter, defaultdict
import json

from ..serialization import write_json
from .config import ROOT
from .modules import xyz
from .signals import output_power
from .transport import DIRECTIONS


def describe(expert):
    operations = expert['operations']
    owner = {xyz(b['position']):i for i,o in enumerate(operations) for b in o['blocks']}
    seen = Counter(xyz(b['position']) for o in operations for b in o['blocks'])
    mechanical, electrical, outputs = [], [], []
    branches = defaultdict(list)
    for child,operation in enumerate(operations):
        p = operation['piston'].get('position')
        if p is None:
            continue
        parent = owner[xyz(p)]
        mechanical.append(dict(parent=parent,child=child,kind=operation['kind'],driver=p,
            delay=operation['start']-operations[parent]['start']))
        branches[parent].append(child)
    ticks = expert['evaluation']['rounds'][0]['ticks']
    powers = [output_power(o['blocks']) for o in operations]
    for target,tick in zip(expert['task']['targets'],ticks):
        p = (target['x'],target['y'],target['z']-2)
        receiver = owner[p]
        suppliers = [i for i,o in enumerate(operations) if p in powers[i] and
                     o['start']+powers[i][p] == tick]
        outputs.append(dict(target=target,unit=receiver,completion_tick=tick,
                            move_start=operations[receiver]['start'],suppliers=suppliers))
        for source in suppliers:
            if source != receiver:
                electrical.append(dict(source=source,receiver=receiver,piston=dict(zip(('x','y','z'),p)),
                    source_start=operations[source]['start'],receiver_start=operations[receiver]['start'],
                    completion_tick=tick,kind='跨单元供电，搬运与输出分时'))
    blocks = {xyz(b['position']): b['block'] for b in expert['proposal']['blocks']}
    mixed = []
    for p,spec in blocks.items():
        if spec['kind'] != 'slime_block':
            continue
        for vector in DIRECTIONS:
            q = tuple(a+b for a,b in zip(p,vector))
            if blocks.get(q,{}).get('kind') == 'honey_block' and owner[p] != owner[q]:
                mixed.append(dict(a=dict(zip(('x','y','z'),p)),b=dict(zip(('x','y','z'),q)),
                                  units=[owner[p],owner[q]],starts=[operations[owner[p]]['start'],operations[owner[q]]['start']]))
    return dict(name=expert['name'],id=expert['id'],task=expert['task'],
        body_blocks=len(blocks),unit_count=len(operations),each_block_moved_once=all(c==1 for c in seen.values()),
        units=[dict(index=i,kind=o['kind'],start=o['start'],end=o['end'],blocks=o['blocks'],
                    size=len(o['blocks']),driver=o['piston']) for i,o in enumerate(operations)],
        mechanical=mechanical,electrical=electrical,outputs=outputs,mixed_material_boundaries=mixed,
        parallel=[dict(parent=p,children=c,starts=[operations[i]['start'] for i in c])
                  for p,c in branches.items() if len(c)>1],
        original_evaluation=expert['evaluation'],
        scope='原件轨迹用于提炼局部机制和连接规则；本报告中的绝对布局及完整连接图不传给需求求解器。')


def main():
    experts = json.loads((ROOT/'expert-audit.json').read_text())
    summaries = []
    for expert in experts:
        result = describe(expert)
        write_json(ROOT/'decomposition'/(expert['id']+'.json'),result)
        summaries.append({k:result[k] for k in ('name','id','unit_count','body_blocks','electrical','parallel')})
    write_json(ROOT/'decomposition-report.json',dict(cases=summaries,mechanisms=[
        '顺向推动串联','反向粘性活塞回拉串联','推拉混合串联','同一驱动单元多路同时分叉',
        '输出活塞先搬运后由后继分支供电','粘液与蜂蜜接触隔离','带釉陶瓦反粘边界',
        '输出目标位于不同前后层','单元只承担传递动作或搬运填充块']))
    print(json.dumps(summaries[-1],ensure_ascii=False))


if __name__ == '__main__':
    main()
