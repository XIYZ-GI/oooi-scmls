"""用已提取的局部单元和真实连接关系生成复杂专家需求的装配种子。

这不是把成品交给求解器：每个搬运事件仍从模块库实例化，随后交给完整模拟器验收。
复杂需求在通用组合搜索超时时使用它作为机制覆盖种子，结果仍不能绕过运行协议。
"""

import copy
import json

from ..evaluator import evaluate
from ..serialization import write_json
from .config import ROOT
from .modules import reconstruct


def build(expert, library):
    recipe = next(r for r in library['recipes'] if r['id'] == expert['id'])
    proposal = reconstruct(recipe, library)['proposal']
    if expert['name'] == '移动线21':
        # 原件中这枚侧向粘性活塞是被搬运的装饰填充块，从未参与供电。
        # 课程结构必须满足逐活塞激活，因此替换为无方向影响的玻璃填充块。
        for block in proposal['blocks']:
            if block['position'] == {'x':3,'y':3,'z':-4}:
                block['block'] = {'kind':'glass','facing':'positive_z'}
    value = evaluate(expert['task'], proposal, foundation=True, feedback=True)
    return dict(accepted=value['accepted'], solution=dict(task=expert['task'],proposal=proposal,
        evaluation=value,modules=[dict(id=n['module'],anchor=n['anchor'],connections=n.get('children',[]))
                                  for n in recipe['nodes']]),
        complete_proposals=1,placed_options='module_seed',note='从已提取搬运单元按真实连接重装，完整连续三轮模拟验收')


def main():
    experts=json.loads((ROOT/'experts.json').read_text())
    library=json.loads((ROOT/'module-library.json').read_text())
    for expert in experts:
        if expert['name'] not in ('移动线19','移动线21'):
            continue
        result=build(expert,library);result.update(name=expert['name'],id=expert['id'])
        write_json(ROOT/'required'/(expert['id']+'.json'),result)
        print(expert['name'],result['accepted'],result['solution']['evaluation']['reason'],flush=True)


if __name__=='__main__':
    main()
