"""批量步进的连续两轮物理预筛；正式验收仍逐刻检查三轮完整协议。"""

import json

import mcscai_engine

from .geometry import point, position


def budget_issue(layout, period):
    """搜索中的超额中间布局属于可回退分支，不应作为原生接口异常退出。"""
    if len(layout.outputs) > 32:
        return '预筛：输出数量超过32个'
    if len(layout.blocks) > 4096 or not 4 <= period <= 1004:
        return '预筛：方块数量或周期超出接口预算'
    return ''


def check(layout, period):
    reason = budget_issue(layout, period)
    if reason:
        return False, reason
    native = getattr(mcscai_engine, 'generator_preflight', None)
    if native is None:
        return reference_check(layout, period)
    return native([(*p, b['kind'], b['facing']) for p,b in sorted(layout.blocks.items())],
                  [(*v['piston'], v['tick']) for v in layout.outputs], period)


def reference_check(layout, period):
    reason = budget_issue(layout, period)
    if reason:
        return False, reason
    engine = mcscai_engine.Simulator()
    def apply(command):
        return json.loads(engine.apply(json.dumps(command,separators=(',',':'))))
    body = layout.payload()
    loads = [dict(position=position((v['piston'][0],v['piston'][1],v['piston'][2]+2+i)),
                  block=dict(kind='iron_block',facing='positive_z'))
             for v in layout.outputs for i in range(10)]
    actuator, power = (0,0,-1),(0,0,-2)
    world = [*body,*loads,
             dict(position=position(actuator),block=dict(kind='piston',facing='positive_z')),
             dict(position=position(power),block=dict(kind='redstone_block',facing='positive_z'))]
    if len({point(b['position']) for b in world}) != len(world):
        return False, '预筛：外部装置或负载重叠'
    initial = apply(dict(type='replace_world',blocks=world))
    ids = {point(b['position']):b['id'] for b in initial['blocks']}
    for cycle in range(2):
        apply(dict(type='step',ticks=4))
        apply(dict(type='remove_block',position=position(power)))
        final = apply(dict(type='step',ticks=period-4))
        actual = {b['id']:point(b['position']) for b in final['blocks']}
        for b in [*body,*loads]:
            x,y,z = point(b['position'])
            if actual.get(ids[x,y,z]) != (x,y,z+cycle+1):
                return False, '预筛：本体或负载未连续平移一格'
        for output in layout.outputs:
            piston_id = ids[output['piston']]
            ticks = [e['tick'] for e in final['events'] if e.get('block_id') == piston_id
                     and e['kind'] == 'piston_extension_completed' and e['tick'] > cycle*period]
            if not ticks or min(ticks) != output['tick']+cycle*period:
                return False, '预筛：输出激活时刻不符'
        if cycle == 0:
            external = next((b for b in final['blocks'] if point(b['position']) == actuator),None)
            if not external or external.get('piston_phase',{}).get('phase') != 'retracted':
                return False, '预筛：外部推动器未回缩'
            apply(dict(type='remove_block',position=position(actuator)))
            actuator = (0,0,0)
            power = (0,0,-1)
            blocked = {point(b['position']) for b in final['blocks'] if b['id'] != external['id']}
            blocked.update(point(b['position']) for b in final['arms'])
            if actuator in blocked or power in blocked:
                return False, '预筛：下一轮推动装置受阻'
            apply(dict(type='set_block',position=position(actuator),block=dict(kind='piston',facing='positive_z')))
            apply(dict(type='set_block',position=position(power),block=dict(kind='redstone_block',facing='positive_z')))
    return True, ''
