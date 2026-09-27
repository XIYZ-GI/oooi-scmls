"""旧第四阶段续训实验的独立目录、固定预算与数据倍数。"""

import os
from pathlib import Path

ROOT=Path('data/generation/expert-expansion')
BASELINE_RECORDS=24894
EXPANDED_RECORDS=BASELINE_RECORDS*5
SEED=2026092205
WORKERS=max(1,min(14,(os.cpu_count() or 2)-2))
INITIAL=Path('data/generation/stage4/accelerated-artifacts/runs/stage4-accelerated/best.pt')
INITIAL_SHA='6078c567541e0fd9e569ea52696d51f9fe4dbab302686aea50603b643c3fca83'

# 保留既有课程入口的资源预算；随机展示入口可以显式扩大。
COMPOSITION_LIMITS = dict(width=16, height=16, depth=9, volume=1024, targets=64)
