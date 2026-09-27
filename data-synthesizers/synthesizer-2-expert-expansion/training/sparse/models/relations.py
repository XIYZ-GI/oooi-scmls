"""每个有符号整数偏移独立查表，联合三轴表达内容相关空间关系。"""

import torch
from torch import nn, Tensor


class ExactRelations(nn.Module):
    def __init__(self, heads: int, extent: int, width: int):
        super().__init__()
        self.limit = extent - 1
        self.heads = heads
        # 训练期由训练器关闭逐批范围的同步校验：布尔判断会把 GPU 流水线排空，
        # 而冻结与批构造阶段已对同一份数据做过范围检查。
        self.strict_checks = True
        self.axes = nn.ModuleList([nn.Embedding(2 * extent - 1, width) for _ in range(3)])
        self.combine = nn.Sequential(nn.Linear(3 * width, 4 * width), nn.GELU(),
                                     nn.Linear(4 * width, 3 * heads))

    def forward(self, coords: Tensor, padding: Tensor) -> Tensor:
        delta = coords[:, :, None, :] - coords[:, None, :, :]
        valid = ~padding[:, :, None] & ~padding[:, None, :]
        if self.strict_checks and bool(((delta.abs() > self.limit).any(-1) & valid).any()):
            raise ValueError('相对格距超出模型范围，禁止截断或合档')
        # 补齐位置不属于设计空间，不能令其虚拟坐标触发越界。
        indices = delta.masked_fill(~valid[..., None], 0) + self.limit
        parts = torch.jit.annotate(list[Tensor], [])
        for axis, embedding in enumerate(self.axes):
            parts.append(embedding(indices[..., axis]))
        relation = self.combine(torch.cat(parts, dim=-1))
        # 三组分别用于纯几何分数、查询内容与几何交互、键内容与几何交互。
        return relation.reshape(coords.size(0), coords.size(1), coords.size(1), 3,
                                self.heads).permute(0, 3, 4, 1, 2)
