"""模型身份、支持范围与正式训练默认配置。"""

MODEL_NAME = 'oooi-scmls-v1-preview-test-1'
ARCHITECTURE = 'unordered_spatial_joint_v1'
FORMAT_VERSION = 1
PROTOCOL = 'unordered_joint_eight_view_v1'
NETWORK = dict(width=224, heads=7, encoder_layers=7, decoder_layers=8,
               relation_width=8, dropout=0.1, max_extent=32, max_volume=1024,
               max_targets=256, max_blocks=1024, activation_checkpoint=True)
RUN = dict(steps=30000, batch_size=32, microbatch=4, attention_budget=1048576,
           learning_rate=0.0001, warmup=1000, weight_decay=0.01, clip_norm=1.0,
           seed=2026092401, precision='bf16', checkpoint_interval=500,
           validation_interval=500, validation_samples=128, log_interval=20,
           push_weight=0.3, full_probability=0.25, empty_probability=0.125,
           augment=True, threads=4, cuda_graph=False, volume_bucket=0, volume_band=0.0,
           max_graphs=24, graph_optimizer=False, prefetch_batches=False, precapture_graphs=False)
CONDITIONING = dict(size=True, targets=True, target_z=False, max_ticks=False,
                    rounds=False, load_blocks=False)
FIXED_PROTOCOL = dict(max_ticks=0, rounds=3, load_blocks=10)
NON_AIR_STATES = 24
