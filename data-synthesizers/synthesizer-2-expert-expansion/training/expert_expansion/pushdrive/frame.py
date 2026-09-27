"""结构搭建画布：占用检查、黏附组记录、推驱中心与目标登记。"""

from copy import deepcopy

AXES = ('x', 'y', 'z')
MATERIALS = ('slime_block', 'honey_block')
SIDE_FACING = {(0, 1): 'positive_y', (0, -1): 'negative_y',
               (1, 0): 'positive_x', (-1, 0): 'negative_x'}
OPPOSITE = dict(positive_x='negative_x', negative_x='positive_x',
                positive_y='negative_y', negative_y='positive_y')
LATERAL = ((1, 0), (-1, 0), (0, 1), (0, -1))


def step(cell, offset, scale=1):
    return (cell[0]+offset[0]*scale, cell[1]+offset[1]*scale, cell[2]+offset[2]*scale)


class Frame:
    """一次结构构造的中间状态；所有坐标都在“前进方向为 +z”的规范坐标系。"""

    def __init__(self, material):
        self.material = material
        self.blocks = {}
        self.targets = []
        self.columns = set()
        self.hubs = []
        self.stages = []
        self.sticky = []
        self.notes = []

    def free(self, cell):
        return cell not in self.blocks

    def put(self, cell, kind, facing='positive_z'):
        if cell in self.blocks:
            return False
        self.blocks[cell] = dict(kind=kind, facing=facing)
        return True

    def piston(self, cell, kind='piston'):
        return self.put(cell, kind, 'positive_z')

    def add_hub(self, charge, observer, style):
        hub = dict(charge=charge, observer=observer, style=style, pistons=[])
        self.hubs.append(hub)
        return hub

    def add_target(self, piston, stage):
        """登记输出目标；要求前方两格空、该列在目标之后没有本体方块。"""
        column = (piston[0], piston[1])
        if column in self.columns:
            return False
        if (column[0], column[1], piston[2]+1) in self.blocks:
            return False
        for cell in self.blocks:
            if cell[0] == column[0] and cell[1] == column[1] and cell[2] >= piston[2]+2:
                return False
        self.columns.add(column)
        self.targets.append(dict(x=piston[0], y=piston[1], z=piston[2]+2, order=stage+1,
                                 stage=stage))
        return True

    def payload(self, push):
        blocks = [dict(position=dict(zip(AXES, cell)), block=dict(self.blocks[cell]))
                  for cell in sorted(self.blocks)]
        targets = [{k: t[k] for k in ('x', 'y', 'z', 'order')} for t in self.targets]
        return dict(blocks=blocks, targets=targets, push=dict(zip(AXES, push)))

    def validate_targets(self):
        """剔除被后续层方块挡住的目标列，保证负载不会被本体或活塞臂占用。"""
        kept, blocked = [], 0
        for target in self.targets:
            column, start = (target['x'], target['y']), target['z']
            if (column[0], column[1], start-1) in self.blocks:
                blocked += 1
                continue
            if any(cell[0] == column[0] and cell[1] == column[1] and cell[2] >= start
                   for cell in self.blocks):
                blocked += 1
                continue
            kept.append(target)
        self.targets = kept
        self.columns = {(t['x'], t['y']) for t in kept}
        return blocked

    def hub_issues(self):
        """静态核对推驱中心：强充能块必须被相邻观察者正对，活塞必须贴该块。"""
        FACING = {'positive_x': (1, 0, 0), 'negative_x': (-1, 0, 0), 'positive_y': (0, 1, 0),
                  'negative_y': (0, -1, 0), 'positive_z': (0, 0, 1), 'negative_z': (0, 0, -1)}
        problems = []
        for stage in self.stages:
            for hub in stage['hubs']:
                charge, observer = hub['charge'], hub['observer']
                spec = self.blocks.get(observer)
                if not spec or spec['kind'] != 'observer':
                    problems.append(('观察者缺失', observer))
                    continue
                direction = FACING[spec['facing']]
                aimed = (observer[0]+direction[0], observer[1]+direction[1], observer[2]+direction[2])
                if aimed != charge:
                    problems.append(('观察者没有正对强充能块', observer))
                for piston in hub['pistons']:
                    if abs(piston[0]-charge[0])+abs(piston[1]-charge[1])+abs(piston[2]-charge[2]) != 1:
                        problems.append(('活塞没有贴着强充能块', piston))
        return problems

    def clone_state(self):
        return (dict(self.blocks), deepcopy(self.targets), set(self.columns),
                deepcopy(self.hubs), deepcopy(self.stages), list(self.sticky))

    def restore(self, state):
        (self.blocks, self.targets, self.columns,
         self.hubs, self.stages, self.sticky) = state
