"""解码器的相对位置偏置：把格距压成有符号对数分档，与网格尺寸解耦。

编码器用的是 ``clamp(-8, 8)`` 的等距档，宽或高超过九格的网格会把更远的距离压成
同一档；而条件向量里的原始坐标量级又随网格尺寸变化，同一个“相距三格”在三格宽和
十五格宽的网格里数值相差数倍。这里对三个轴分别用「距离分档表 + 符号表」表示相对
位置：分档覆盖到 32 格，与尺寸无关；符号表单独存在，模型既容易学到镜像对称的偏置
（左右镜像下分档不变、符号翻转），也保留了必要时的方向性。
"""

import torch
from torch import nn

# 能表示的最大格距；超过后并入最高档，覆盖训练与网页输入的全部网格尺寸。
MAX_OFFSET = 32
# 档位数量：0、1、2、3、4~5、6~8、9~12、13~18、19 以上。
LEVELS = 9
# 绝对格距到档位的查表，索引即格距。
MAGNITUDE_LEVELS = ([0, 1, 2, 3, 4, 4, 5, 5, 5] + [6]*4 + [7]*6 + [8]*14)


class RelativeBias(nn.Module):
    """按轴计算格距偏置，形状 ``(批, 头, 查询位, 键位)``，可直接当注意力浮点掩码。"""

    def __init__(self, heads, axes=3):
        super().__init__()
        self.heads = heads
        self.magnitude = nn.ModuleList([nn.Embedding(9, heads) for _ in range(axes)])
        self.sign = nn.ModuleList([nn.Embedding(3, heads) for _ in range(axes)])
        self.register_buffer('magnitude_index', torch.tensor(MAGNITUDE_LEVELS, dtype=torch.long),
                             persistent=False)

    def forward(self, query, key):
        delta = query[:, :, None, :].long() - key[:, None, :, :].long()
        offset = delta.abs().clamp(max=32)
        sign = delta.sign() + 1
        bias = 0
        for axis, (magnitude, sign_table) in enumerate(zip(self.magnitude, self.sign)):
            bias = bias + magnitude(self.magnitude_index[offset[..., axis]]) + sign_table(sign[..., axis])
        return bias.permute(0, 3, 1, 2)
