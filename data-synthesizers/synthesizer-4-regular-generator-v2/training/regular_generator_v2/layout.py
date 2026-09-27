"""独立方块布局与三维归一；保留全部目标和预设时序。"""

from .config import LIMITS, LOAD_BLOCKS, MAX_TICKS, ROUNDS, VERSION


class Layout:
    def __init__(self):
        self.blocks = {}
        self.targets = []
        self.push = None
        self.groups = []

    def put(self, x, y, z, kind, facing='positive_z'):
        p = x, y, z
        if p in self.blocks:
            raise ValueError('构造方块位置重叠')
        self.blocks[p] = dict(kind=kind, facing=facing)

    def output(self, x, y, z, order):
        self.put(x, y, z, 'piston')
        self.targets.append(dict(x=x, y=y, z=z+2, order=order))

    def record_group(self, before, anchor, order):
        added = set(self.blocks)-before
        if len(added) > 12:
            raise ValueError('构造运动组超过十二块')
        self.groups.append(dict(anchor=anchor, order=order, blocks=len(added)))

    def pack(self, plan):
        if not self.blocks or self.push not in self.blocks:
            raise ValueError('布局或推动点为空')
        ox, oy = (min(p[a] for p in self.blocks) for a in (0, 1))
        oz = max(p[2] for p in self.blocks)+2
        def position(p):
            return dict(x=p[0]-ox, y=p[1]-oy, z=p[2]-oz)
        blocks = [dict(position=position(p), block=dict(b)) for p, b in sorted(self.blocks.items())]
        targets = [{**position((t['x'], t['y'], t['z'])), 'order': t['order']} for t in self.targets]
        width = max(b['position']['x'] for b in blocks)+1
        height = max(b['position']['y'] for b in blocks)+1
        depth = oz-min(p[2] for p in self.blocks)-1
        if not 2 <= depth <= LIMITS['depth']:
            raise ValueError('实际厚度不在二至六格')
        if width > LIMITS['width'] or height > LIMITS['height'] or len(targets) > LIMITS['targets']:
            raise ValueError('构造超出生成器资源上限')
        if len(blocks) > LIMITS['blocks'] or len({(t['x'], t['y']) for t in targets}) != len(targets):
            raise ValueError('方块超额或目标列重复')
        core = dict(x=-ox, y=(-1 if plan.get('rows', 2) == 3 else 0)-oy,
                    width=sum(plan['widths']), height=plan.get('rows', 2))
        return dict(source=VERSION, family=plan['profile'], plan={**plan, 'core': core},
                    task=dict(width=width, height=height, depth=depth, targets=targets,
                              rounds=ROUNDS, load_blocks=LOAD_BLOCKS, max_ticks=MAX_TICKS),
                    proposal=dict(blocks=blocks, push=position(self.push)),
                    construction=dict(groups=self.groups))
