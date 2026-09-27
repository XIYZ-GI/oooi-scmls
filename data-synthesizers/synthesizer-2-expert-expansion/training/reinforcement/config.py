"""第五阶段训练与验收的可追溯初始配置。"""

PLAN = {
    'seed': 20260921, 'iterations': 300, 'rollouts': 256, 'generation_batch': 64,
    'minibatch': 32, 'ppo_epochs': 2, 'learning_rate': 1e-5,
    'clip_ratio': 0.2, 'value_weight': 0.5, 'entropy_weight': 0.003,
    'reference_kl_weight': 0.02, 'target_kl': 0.025, 'temperature': 0.85,
    'workers': 12, 'checkpoint_interval': 25, 'validation_interval': 50,
    'max_training_seconds': 10800, 'candidates': 8, 'evaluation_seed': 41,
    'initial_checkpoint': 'data/generation/stage5/initial.pt',
    'demand_mix': {'expert': 0.2, 'random': 0.6, 'success': 0.2},
    'depth_weights': {'2': 0.4, '3': 0.4, '4': 0.2},
    'success_gate': {'heldout_gain': 8, 'heldout_multigroup_gain': 2,
                     'web_gain': 2, 'expert_max_regression': 1},
    'scope': '新随机目标几何的固定八视角完整通过率；不将部分奖励或训练需求复现作为验收',
}
