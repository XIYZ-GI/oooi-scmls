"""整份方块布局、待连接接口及可回退的编辑状态。"""

from .config import LIMITS
from .geometry import position


class Layout:
    def __init__(self, low, high):
        self.low, self.high = low, high
        self.blocks = {}
        self.outputs = []
        self.links = []
        self.operations = []
        self.reserve_outputs = False

    def free(self, p):
        return (not (self.reserve_outputs and any(p[:2] == v['piston'][:2] and p[2] > v['piston'][2]
                                                for v in self.outputs))
                and self.low <= p[2] <= self.high and p not in self.blocks
                and abs(p[0]) < LIMITS['width'] and abs(p[1]) < LIMITS['height'])

    def put(self, p, kind, facing='positive_z'):
        if not self.free(p):
            return False
        if kind not in ('observer', 'piston', 'sticky_piston'):
            facing = 'positive_z'
        self.blocks[p] = dict(kind=kind, facing=facing)
        return True

    def checkpoint(self):
        return self._copy_state((self.blocks, self.outputs, self.links, self.operations))

    def restore(self, checkpoint):
        self.blocks, self.outputs, self.links, self.operations = self._copy_state(checkpoint)

    @staticmethod
    def _copy_state(state):
        # 坐标为元组，类型、朝向及刻数不可变；只复制可编辑的字典和列表。
        blocks, outputs, links, operations = state
        return ({p:dict(b) for p,b in blocks.items()},
                [dict(v) for v in outputs], [dict(v) for v in links],
                [{**v,'charges':list(v['charges']),'added':list(v['added'])} for v in operations])

    def payload(self):
        return [dict(position=position(p), block=dict(b)) for p, b in sorted(self.blocks.items())]
