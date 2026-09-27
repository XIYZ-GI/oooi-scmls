"""需求编码层和动态空间解码层；没有序列因果或编号递增掩码。"""

from torch import nn, Tensor

from .attention import SpatialAttention


class SpatialLayer(nn.Module):
    def __init__(self, width: int, heads: int, dropout: float, cross: bool):
        super().__init__()
        self.cross = cross
        self.norm1 = nn.LayerNorm(width)
        self.self_attention = SpatialAttention(width, heads, dropout)
        self.norm2 = nn.LayerNorm(width) if cross else nn.Identity()
        # 编码层也保留相同调用签名，不创建未使用的可训练参数。
        self.cross_attention = SpatialAttention(width, heads, dropout) if cross else None
        self.memory_norm = nn.LayerNorm(width) if cross else nn.Identity()
        self.norm3 = nn.LayerNorm(width)
        self.ffn = nn.Sequential(nn.Linear(width, 4 * width), nn.GELU(), nn.Dropout(dropout),
                                 nn.Linear(4 * width, width))
        self.dropout = nn.Dropout(dropout)

    def forward(self, value: Tensor, memory: Tensor, relation: Tensor,
                padding: Tensor) -> Tensor:
        normalized = self.norm1(value)
        value = value + self.dropout(self.self_attention(normalized, normalized, relation, padding))
        if self.cross_attention is not None:
            value = value + self.dropout(self.cross_attention(self.norm2(value), self.memory_norm(memory),
                                                              relation, padding))
        value = value + self.dropout(self.ffn(self.norm3(value)))
        return value.masked_fill(padding[..., None], 0.0)
