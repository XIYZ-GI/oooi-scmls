"""根据实际供电来源检查入口延伸的前后位置与满位输出条件。"""


def counts(evidence):
    links = [v for v in evidence['links'] if v['kind']=='pull']
    def number(predicate):
        return sum(any(s['extended_input'] and predicate(s) for s in v['supply_layouts']) for v in links)
    return dict(front=number(lambda s:s['driver_depth_offset']>0),
                rear=number(lambda s:s['driver_depth_offset']<=0),
                saturated_front=number(lambda s:s['driver_depth_offset']>0 and s['primary_outputs']>=4),
                saturated_rear=number(lambda s:s['driver_depth_offset']<=0 and s['primary_outputs']>=4))


def issue(evidence,options):
    if evidence['extended_input_pulls'] < options.get('min_extensions',0):
        return '有效入口延伸拉驱不足'
    placement = options.get('extension_placement','any')
    if placement != 'any' and counts(evidence)[placement] < max(1,options.get('min_extensions',0)):
        return '有效入口延伸未满足指定的前后位置'
    saturated = (evidence['saturated_extension_pulls'] if placement == 'any'
                 else counts(evidence)['saturated_'+placement])
    if saturated < options.get('min_saturated_extensions',0):
        return '前端四输出满位的有效入口延伸不足'
    return ''
