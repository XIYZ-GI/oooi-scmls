"""训练 ``oooi-scmls-v1.1-preview``：网络与 v1-preview 同宽同深，换精确相对位置编码。

训练数据、步数、学习率、预热与随机种子与 v1-preview 完全一致，因此两组结果可以
直接对照：差异只来自数据覆盖面与相对位置编码这两项。
"""

import argparse

from .config import (LEARNING_RATE, EXACT_RELATIVE, EXACT_RELATIVE_PARAMETERS, SEED, STEPS,
                     WARMUP, experiment)
from .train import run


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="", help="实验目录，默认 data/generation/oooi-scmls-v1.1-preview")
    args = parser.parse_args()
    run(root=args.root or experiment("oooi-scmls-v1.1-preview"), config=EXACT_RELATIVE,
        parameters=EXACT_RELATIVE_PARAMETERS, steps=STEPS, seed=SEED,
        learning_rate=LEARNING_RATE, warmup=WARMUP)
