"""具有内容相关三维关系分数的多头注意力。"""

import torch
from torch import nn, Tensor
from typing import Optional
from torch.nn import functional as F


class SpatialAttention(nn.Module):
    def __init__(self, width: int, heads: int, dropout: float):
        super().__init__()
        self.heads = heads
        self.head_width = width // heads
        self.dropout = dropout
        self.query = nn.Linear(width, width)
        self.key = nn.Linear(width, width)
        self.value = nn.Linear(width, width)
        self.output = nn.Linear(width, width)
        self.query_geometry = nn.Linear(width, heads)
        self.key_geometry = nn.Linear(width, heads)
        self.scales = nn.Parameter(torch.ones(3, heads))

    def split(self, value: Tensor) -> Tensor:
        return value.reshape(value.size(0), value.size(1), self.heads,
                             self.head_width).transpose(1, 2)

    def gates(self, query: Tensor, memory: Tensor):
        """查询与键内容门控；增量解码要按位置缓存键侧门控，因此单独暴露。"""
        return (self.query_geometry(query).tanh().transpose(1, 2).unsqueeze(-1),
                self.key_geometry(memory).tanh().transpose(1, 2).unsqueeze(-2))

    def bias_from_gates(self, qgate: Tensor, kgate: Tensor, relation: Tensor, padding: Tensor,
                        causal: bool = False, dtype: Optional[torch.dtype] = None) -> Tensor:
        """关系分数与门控的合成；因果与补齐在最后一次性屏蔽。

        单独拆出来是为了让逐位置增量解码能只算当前查询那一行，仍与整段前向
        共用同一套分数，避免两条路径出现偏差。
        """
        geometry, scales = relation.to(dtype), self.scales.to(dtype)
        value = (geometry[:, 0] * scales[0][None, :, None, None]
                 + geometry[:, 1] * qgate.to(dtype) * scales[1][None, :, None, None]
                 + geometry[:, 2] * kgate.to(dtype) * scales[2][None, :, None, None])
        blocked = padding[:, None, None, :]
        if causal:
            # 自注意力的因果屏蔽与补齐掩码合进同一张浮点偏置。
            blocked = blocked | torch.ones(value.shape[-2], value.shape[-1], dtype=torch.bool,
                                           device=value.device).triu(1)
        return value.masked_fill(blocked, float('-inf'))

    def bias(self, query: Tensor, memory: Tensor, relation: Tensor, padding: Tensor,
             causal: bool = False, dtype: Optional[torch.dtype] = None) -> Tensor:
        qgate, kgate = self.gates(query, memory)
        return self.bias_from_gates(qgate, kgate, relation, padding, causal,
                                    query.dtype if dtype is None else dtype)

    def forward(self, query: Tensor, memory: Tensor, relation: Tensor,
                padding: Tensor, causal: bool = False) -> Tensor:
        q, k, v = self.split(self.query(query)), self.split(self.key(memory)), self.split(self.value(memory))
        # 位置偏置是每层最大的中间张量（批×头×格×格）。它只作为注意力的加性分数，
        # 全程在计算精度内合成即可，保持 float32 会多出一倍的带宽与一次整体类型转换。
        bias = self.bias(query, memory, relation, padding, causal, q.dtype)
        value = F.scaled_dot_product_attention(q, k, v, attn_mask=bias,
                                               dropout_p=self.dropout if self.training else 0.0)
        return self.output(value.transpose(1, 2).flatten(2))
