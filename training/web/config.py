"""网页生成服务的目录约定与固定协议。

两个目录都可以用环境变量覆盖，容器里分别挂到 ``/app/data`` 与 ``/app/models``：

* ``MCSCAI_DATA_DIR``：任务、草稿、回放的持久化目录（SQLite 与逐任务文件夹）。
* ``MCSCAI_MODELS_DIR``：模型权重与 ``models.json`` 注册表所在的目录。
"""

import os
from pathlib import Path

# 生成任务的持久化根目录，默认是仓库根下的 data/。
ROOT = Path(os.getenv("MCSCAI_DATA_DIR", "data")) / "generation"
# 网页生成任务的工作区：SQLite 数据库与每个任务一个子目录。
STORE = ROOT / "web"
# 模型目录：权重与注册表。
MODELS = Path(os.getenv("MCSCAI_MODELS_DIR", "models"))
# 注册表文件名固定，路径条目相对本目录解析，禁止越界。
REGISTRY = MODELS / "models.json"

# 前八个候选是八视角确定性贪心解码，额外候选按温度采样。协议名随结果一起保存。
PROTOCOL = "eight_view_greedy_v1"
SAMPLED_PROTOCOL = "eight_view_greedy_then_sample_v1"
DEFAULT_CANDIDATES = 8
MAX_CANDIDATES = 64
SAMPLING_TEMPERATURE = 0.7
DEFAULT_TASK = dict(width=7, height=5, depth=2, targets=[], max_ticks=48, rounds=3, load_blocks=10)
