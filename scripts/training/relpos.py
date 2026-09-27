"""训练 ``oooi-scmls-v1-preview``：十二维需求 + 解码器相对位置偏置。

数据集由 ``scripts.training.dataset`` 冻结，默认目录
``data/generation/oooi-scmls-v1-preview/``。训练结束后用
``scripts.training.evaluate`` 跑四套百题，再用 ``scripts.training.deploy`` 发布权重。
"""

import argparse

from .config import (LEARNING_RATE, RELATIVE_POSITION, RELATIVE_POSITION_PARAMETERS, SEED, STEPS,
                     WARMUP, experiment)
from .train import run


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="", help="实验目录，默认 data/generation/oooi-scmls-v1-preview")
    args = parser.parse_args()
    run(root=args.root or experiment("oooi-scmls-v1-preview"), config=RELATIVE_POSITION,
        parameters=RELATIVE_POSITION_PARAMETERS, steps=STEPS, seed=SEED,
        learning_rate=LEARNING_RATE, warmup=WARMUP)
