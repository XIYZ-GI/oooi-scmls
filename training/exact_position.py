"""``oooi-scmls-v1.1-preview`` 使用的精确三维相对位置编码。

``oooi-scmls-v1-preview`` 的编码器用 ``clamp(-8, 8)`` 的等距档，解码器用九档
「距离分档＋符号表」。这里换成三轴每个有符号整数格距独立查表、不合档也不截断的
表示，联合出一个每头三组的关系分数（纯几何、查询内容门控、键内容门控）。
两个版本共用 ``relations`` 里的注意力实现，保证相对位置编码只有一份代码。
"""

from torch import nn, Tensor

from .relations.attention import SpatialAttention
from .relations.layers import SpatialLayer
from .relations.relations import ExactRelations

__all__ = ['CausalCrossLayer', 'ExactRelations', 'SpatialLayer']


class CausalCrossLayer(nn.Module):
    """与 ``SpatialLayer`` 同式的解码层：自注意力因果，交叉注意力取真实格子为键。

    旧生成器按格子遍历顺序逐位输出方块，解码端必须保持因果；稀疏模型是整段
    联合细化，没有因果要求，因此这里只在自注意力上补一张上三角屏蔽，其余
    归一化、残差、前馈与补齐处理与 ``SpatialLayer`` 保持一致。
    """

    def __init__(self, width: int, heads: int, dropout: float):
        super().__init__()
        self.norm1 = nn.LayerNorm(width)
        self.self_attention = SpatialAttention(width, heads, dropout)
        self.norm2 = nn.LayerNorm(width)
        self.cross_attention = SpatialAttention(width, heads, dropout)
        self.memory_norm = nn.LayerNorm(width)
        self.norm3 = nn.LayerNorm(width)
        self.ffn = nn.Sequential(nn.Linear(width, 4 * width), nn.GELU(), nn.Dropout(dropout),
                                 nn.Linear(4 * width, width))
        self.dropout = nn.Dropout(dropout)

    def forward(self, value: Tensor, memory: Tensor, self_relation: Tensor, self_padding: Tensor,
                cross_relation: Tensor, cross_padding: Tensor) -> Tensor:
        normalized = self.norm1(value)
        value = value + self.dropout(self.self_attention(normalized, normalized, self_relation,
                                                         self_padding, causal=True))
        value = value + self.dropout(self.cross_attention(self.norm2(value), self.memory_norm(memory),
                                                          cross_relation, cross_padding))
        value = value + self.dropout(self.ffn(self.norm3(value)))
        return value.masked_fill(self_padding[..., None], 0.0)


def decoder_relations(relation: Tensor, length: int):
    """按已解码长度切出自注意力与交叉注意力的关系分数。"""
    return relation[:, :, :, :length, :length], relation[:, :, :, :length]
