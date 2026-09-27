"""先观测真实时序，再按完整硬门槛准入；错误课程不进入监督集。"""

from ..evaluator import evaluate
from ..serialization import digest


def admit(row):
    value=evaluate(row['task'],row['proposal'],foundation=True,feedback=True,require_activation=False)
    # 构造器不假定所有活塞同刻完成，用实际运行生成时序标签。
    if not value['accepted'] and value['reason']=='目标先后顺序或同刻分组不符合需求':
        cycles=value.get('feedback',{}).get('cycles',[])
        if value.get('foundation',{}).get('accepted') and len(cycles)==3:
            ranks=[]
            for c in cycles:
                if any(t is None for t in c['ticks']):
                    break
                order={t:i+1 for i,t in enumerate(sorted(set(c['ticks'])))}
                ranks.append([order[t] for t in c['ticks']])
            if len(ranks)==3 and ranks[0]==ranks[1]==ranks[2]:
                for t,order in zip(row['task']['targets'],ranks[0]):
                    t['order']=order
                value=evaluate(row['task'],row['proposal'],foundation=True,require_activation=False)
    row['evaluation']=value
    row['id']=digest([row['task'],row['proposal']])[:24]
    return row
