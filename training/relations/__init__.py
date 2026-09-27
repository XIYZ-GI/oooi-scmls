"""精确三维相对位置关系、空间注意力与编码／解码层。

``oooi-scmls-v1-preview`` 用九档「距离分档＋符号表」表达相对位置，
``oooi-scmls-v1.1-preview`` 换成这里的三轴有符号整数格距独立嵌入。两个模型共用
同一份注意力实现，区别只在于关系分数怎么算，因此编码器与解码层放在这里统一维护。
"""

from .attention import SpatialAttention
from .layers import SpatialLayer
from .relations import ExactRelations

__all__ = ["SpatialAttention", "SpatialLayer", "ExactRelations"]
