"""原随机生长器的中小尺寸、实心目标偏好与随机拉驱树需求。"""

from .layout import Layout
from ..regular_generator_v2.rectangles import rectangles


class RegularLayout(Layout):
    def __init__(self, low, high, width, height):
        super().__init__(low, high)
        self.width, self.height = width, height

    def free(self, p):
        layers = getattr(self, 'placing_layers', None)
        if layers is not None and not layers[0] <= p[2] <= layers[1]:
            return False
        if not super().free(p):
            return False
        points = [*self.blocks, p]
        return all(max(q[a] for q in points)-min(q[a] for q in points) < limit
                   for a, limit in enumerate((self.width, self.height)))


def request(rng, category, options):
    """随机链深、推拉分叉与叶组输出量，不包含预制坐标或固定扇出骨架。"""
    if options.get('mixed', True):
        if options.get('layered', True):
            if options.get('depth', 4) == 4 and options.get('rectangular_seed'):
                from .layered_rectangle_plan import request as rectangular_request
                return rectangular_request(rng, options.get('fan_end_observers'))
            from .multilayer_plan import request as multilayer_request
            return multilayer_request(rng, options.get('depth', 4), category)
        from .regular_mixed_plan import request as mixed_request
        return mixed_request(rng)
    if options.get('fanout_plan'):
        from .regular_branch_plan import request as branch_request
        result = branch_request(rng)
        if options.get('route_first'):
            reserve_outputs(result)
        return result
    levels = rng.randint(3, 4) if category == '推拉结合多时序' else 2
    reserve = options.get('reserve_branches', False)
    remaining = [rng.randint(levels+2, levels+5) if reserve else rng.randint(levels+1, levels+3)]

    def node(level):
        remaining[0] -= 1
        children = []
        if level and remaining[0]:
            children.append(('pull', node(level-1)))
            if remaining[0] and rng.random() < .55:
                children.append(('pull', node(rng.randrange(level))))
        outputs = ((1, rng.randint(1, 3)) if children else (3, rng.randint(5, 7))) if reserve else (2, rng.randint(4, 7))
        return dict(outputs=outputs, children=children)

    if category != '推拉结合多时序':
        raise ValueError('规律随机生长目前要求推拉结合多时序类别')
    result = node(levels)
    if options.get('route_first'):
        reserve_outputs(result)
    return result


def reserve_outputs(node):
    """每组保留一个时序验证输出，其余空位留给后继布线完成后补齐。"""
    node['outputs'] = (1, 1)
    for _, child in node['children']:
        reserve_outputs(child)


def prioritize(outputs, layout, tick=None):
    """优先填补现有目标的二维实心缺口，随后才扩张截面；随机顺序保留作同分裁决。"""
    points = {v['piston'][:2] for v in layout.outputs}
    simultaneous = {v['piston'][:2] for v in layout.outputs if v['tick'] == tick}
    body = {p[:2] for p in layout.blocks}

    def score(p):
        x, y = p[:2]
        group = simultaneous if tick is not None else points
        square = sum(all((x+dx, y+dy) in group for dx, dy in offsets)
                     for offsets in (((1, 0), (0, 1), (1, 1)),
                                     ((-1, 0), (0, 1), (-1, 1)),
                                     ((1, 0), (0, -1), (1, -1)),
                                     ((-1, 0), (0, -1), (-1, -1))))
        neighbors = sum((x+dx, y+dy) in points for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        section = body | {(x, y)}
        area = (max(q[0] for q in section)-min(q[0] for q in section)+1)*(
            max(q[1] for q in section)-min(q[1] for q in section)+1)
        if getattr(layout, 'large_regions', False):
            regions = rectangles(group | {(x, y)})
            return -(regions[0]['area'] if regions else 0), -square, -neighbors, area
        return -square, -neighbors, area

    outputs.sort(key=score)
