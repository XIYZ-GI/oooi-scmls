"""第二轮固定路径与有限训练预算。"""

from pathlib import Path

DATA = Path('data/generation/stage3-round2')
RUNS = Path('runs/stage3-round2')
PLAN = {
    'seed': 20260926, 'steps': 9000, 'batch_size': 12, 'learning_rate': 0.00010,
    'initial_checkpoint': 'runs/stage3/last.pt', 'validation_interval': 1500,
    'family_sampling': {'mixed_three': 0.30, 'mixed_two': 0.20, 'strong_compact': 0.20,
                        'pull_compact': 0.15, 'expert_compact': 0.10, 'legacy': 0.05},
    'selection_candidates': 4, 'final_candidates': 8, 'max_training_seconds': 2700,
    'selection': '先最大化强充能、两时序混材、三时序混材、旧拉驱四族完整验证通过率的最小值，再比较均值，平分取较早检查点。混材还必须有相邻异材分别运动证据。',
    'scope': '混材派生保持原专家训练来源身份，usage额外区分拟合、开发和新目标组合评估；不能宣称源外专家泛化。',
    'new_training_runs': 1,
}
