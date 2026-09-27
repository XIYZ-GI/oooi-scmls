"""两个发布模型的训练配置、实验目录与评估协议。

网络宽度、头数、层数、步数、学习率、预热与随机种子在两个模型之间完全一致，
唯一的结构差异是相对位置编码，因此两组损失曲线与四套百题成绩可以直接对照。
"""

from pathlib import Path

# 数据与实验产物的根目录，可用 --root 覆盖。
DATA = Path("data")
GENERATION = DATA / "generation"

# 训练公共协议。
STEPS = 30000
LEARNING_RATE = 3e-4
WARMUP = 200
SEED = 2026092209

# 评估协议：八视角确定性贪心，每套题八个候选，与网页推理页同一判定口径。
CANDIDATES = 8
SUITES = ("today100", "historical200", "historical188", "previous300")

# 需求特征口径：几何九项加目标三项，共十二维；不含目标 z、每轮刻数与连续轮数。
FEATURE_SPEC = "12 维需求（几何九项、目标三项，不含目标 z 与运行协议）"

# ``oooi-scmls-v1-preview``：编码器等距档、解码器九档「距离分档＋符号表」。
RELATIVE_POSITION = dict(width=224, heads=7, encoder_layers=7, decoder_layers=8, dropout=0.1,
                         use_target_z=False, use_run_features=False, decoder_relative=True)
RELATIVE_POSITION_PARAMETERS = 10808901

# ``oooi-scmls-v1.1-preview``：换成三轴有符号整数格距独立嵌入的精确相对位置编码。
EXACT_RELATIVE = dict(width=224, heads=7, encoder_layers=7, decoder_layers=8, dropout=0.1,
                      use_target_z=False, use_run_features=False, decoder_relative=False,
                      exact_relative=True, relation_width=8, relation_extent=32)
EXACT_RELATIVE_PARAMETERS = 10887548


def experiment(name):
    """实验目录：``data/generation/<实验名>/``，数据、断点、评估结果都放在下面。"""
    return GENERATION / name
