"""移动线结构生成器v2：实心目标区域与规律时序的独立合成入口。"""

from .metrics import describe_targets
from .compactness import describe_compactness
from .worker import generate
from .campaign import requests as campaign_requests
from .campaign_admission import batch_report
from .fan import build_fan
from .solid_regions import describe_regions

__all__ = ['describe_targets', 'describe_compactness', 'generate', 'campaign_requests',
           'batch_report', 'build_fan', 'describe_regions']
