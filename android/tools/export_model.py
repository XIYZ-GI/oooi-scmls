"""把移动线生成模型导出为 TorchScript，供安卓端 PyTorch Lite 加载。

为什么导出侧要重新实现前向：`training/model.py` 的 `encode` / `decode` / `push_logits`
把需求放进化名 `batch` 的字典里传递，而这些方法**没有类型标注**。TorchScript 对未标注
参数一律按 `Tensor` 处理，于是 `batch["features"]` 会被编译成「用字符串索引张量」而报错。
给生产代码加标注会改到服务器在用的实现，因此这里改用显式张量参数重新实现同一套前向：
直接复用模型的各个子模块（编码器、解码器、相对位置偏置、两个输出头），只是不再经过字典。

重复的规模约四十行，风险由导出末尾的数值一致性校验兜住：导出的贪心生成结果必须与
`training.inference.generate` 逐候选一致，任何偏差都会改变某个位置的 argmax 而被抓住。

八视角候选的截面变换发生在**需求侧**（先变换需求、生成后再逆变换），因此这里按一批需求
同时生成，批大小即视角数；模型本身不需要知道视角的存在。

用法：

    .tools/training-venv/bin/python -m android.tools.export_model

产出（默认写入 `android/app/src/main/assets/`）：

    oooi-scmls-v1-preview.pt     TorchScript 模块
    oooi-scmls-v1-preview.json   元数据：网络配置、特征列数、状态词表与来源摘要
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import torch
from torch import nn

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from android.tools.position_patch import load_patched_position  # noqa: E402
from android.tools.cached_decoder import CachedDecoder  # noqa: E402
from training.constants import BOS, STATES  # noqa: E402
from training.data import condition, feature_count  # noqa: E402
from training.serialization import decode_structure, positions  # noqa: E402

DEFAULT_CHECKPOINT = (
    ROOT
    / "models"
    / "oooi-scmls-v1-preview.pt"
)
DEFAULT_OUTPUT = ROOT / "android/app/src/main/assets"
MODEL_STEM = "oooi-scmls-v1-preview"

# 与 `training/constants.py` 保持一致；TorchScript 不接受闭包捕获的模块级常量，
# 因此这些值在下面以字面量出现，改动时必须与 Python 侧同步。
STATE_COUNT = len(STATES)
BOS_TOKEN = BOS


class AndroidGenerator(nn.Module):
    """只含推理路径的生成器：显式张量入参，子模块直接复用已训练权重。"""

    def __init__(self, model: nn.Module):
        super().__init__()
        # 直接接管已训练的子模块，权重共享，不复制参数。
        self.condition = model.condition
        self.tokens = model.tokens
        self.relative = model.relative
        self.adjacency = model.adjacency
        self.encoder = model.encoder
        self.memory_norm = model.memory_norm
        self.decoder = model.decoder
        self.block_head = model.block_head
        self.push_head = model.push_head
        self.decoder_relative = model.decoder_relative
        self.decoder_cross_relative = model.decoder_cross_relative
        self.cached_decoder = CachedDecoder(model)

    def encode(self, features: torch.Tensor, coords: torch.Tensor,
               padding: torch.Tensor) -> torch.Tensor:
        """关系编码器；对应 `Generator.encode` 的显式张量版本。"""
        # 安卓侧造不出 bool 张量：Lite 的 `Tensor.fromBlob` 只支持 byte/int/long/float/
        # double，bool 与 int8 都没有重载，因此 padding 只能用 uint8 的 0/1 送进来。
        # 而 masked_fill 只接受布尔掩码，dtype 不对会直接抛异常。入口处统一转成 bool，
        # 使 bool（Python 侧调用）与 uint8（安卓侧调用）两种传法都能用。
        padding = padding.to(torch.bool)
        value = self.condition(features)
        delta = coords[:, :, None, :] - coords[:, None, :, :]
        bias = torch.zeros(delta.shape[0], delta.shape[1], delta.shape[1],
                           self.relative[0].weight.shape[1],
                           dtype=value.dtype, device=value.device)
        # `ModuleList` 的下标必须是字面量，因此三个轴逐个展开而不是循环。
        bias = bias + self.relative[0](delta[..., 0].clamp(-8, 8) + 8)
        bias = bias + self.relative[1](delta[..., 1].clamp(-8, 8) + 8)
        bias = bias + self.relative[2](delta[..., 2].clamp(-8, 8) + 8)
        bias = bias + self.adjacency((delta.abs().sum(-1) == 1).long())
        bias = bias.permute(0, 3, 1, 2).masked_fill(padding[:, None, None, :],
                                                    float("-inf"))
        bias = bias.flatten(0, 1)
        for layer in self.encoder:
            value = layer(value, bias)
        return self.memory_norm(value)

    def decode(self, inputs: torch.Tensor, features: torch.Tensor, coords: torch.Tensor,
               padding: torch.Tensor, memory: torch.Tensor):
        """解码一步；对应 `Generator.decode` 的显式张量版本。"""
        # 与 encode 同理：外部可能送来 uint8，掩码运算只接受布尔。这里也归一，
        # 否则 `~padding` 在 uint8 下得到 254 而不是 false，掩码会完全失效。
        padding = padding.to(torch.bool)
        length = inputs.shape[1]
        embedded = self.tokens(inputs) + self.condition(features[:, :length])
        causal = torch.ones(length, length, dtype=torch.bool,
                            device=inputs.device).triu(1)
        if self.decoder_relative is None:
            hidden = self.decoder(embedded, memory, tgt_mask=causal,
                                  tgt_key_padding_mask=padding[:, :length],
                                  memory_key_padding_mask=padding, tgt_is_causal=True)
        else:
            self_bias = self.decoder_relative(coords[:, :length], coords[:, :length])
            self_bias = self_bias.masked_fill(causal[None, None], float("-inf"))
            self_bias = self_bias.masked_fill(padding[:, None, None, :length],
                                              float("-inf"))
            cross_bias = self.decoder_cross_relative(coords[:, :length], coords)
            cross_bias = cross_bias.masked_fill(padding[:, None, None, :],
                                                float("-inf"))
            hidden = self.decoder(embedded, memory,
                                  tgt_mask=self_bias.flatten(0, 1).to(embedded.dtype),
                                  memory_mask=cross_bias.flatten(0, 1).to(embedded.dtype),
                                  tgt_is_causal=False, memory_is_causal=False)
        return self.block_head(hidden), hidden

    def push_logits(self, hidden: torch.Tensor, tokens: torch.Tensor,
                    coords: torch.Tensor, padding: torch.Tensor) -> torch.Tensor:
        """推动点打分；对应 `Generator.push_logits` 的显式张量版本。"""
        scores = self.push_head(hidden + self.tokens(tokens.clamp(min=0))).squeeze(-1)
        # 25 同样是 `STATES` 的长度，不能引用模块级常量。
        occupied = (tokens > 0) & (tokens < 25) & ~padding
        same_column = (coords[:, :, None, :2] == coords[:, None, :, :2]).all(-1)
        behind = coords[:, None, :, 2] < coords[:, :, None, 2]
        accessible = occupied & ~(same_column & behind & occupied[:, None, :]).any(-1)
        # 全空气候选保留有限分数，随后由精确评估器明确拒绝。
        scores = scores.masked_fill(~accessible, -1e4)
        return scores.masked_fill(padding, -1e9)

    @torch.jit.export
    def generate(self, features: torch.Tensor, coords: torch.Tensor,
                 padding: torch.Tensor, temperature: float):
        """按需求批量贪心或采样生成；返回 token 序列与推动点下标。

        形状：`features` 为 (批, 网格, 特征列)，`coords` 为 (批, 网格, 3)，
        `padding` 为 (批, 网格) 的补齐掩码；bool 与 uint8 都可以，内部统一按布尔处理。
        """
        padding = padding.to(torch.bool)
        memory = self.encode(features, coords, padding)
        tokens, hidden = self.cached_decoder(self.condition(features), memory, coords,
                                             padding, temperature)
        scores = self.push_logits(hidden, tokens, coords, padding)
        return tokens, scores.argmax(-1)

    def forward(self, features: torch.Tensor, coords: torch.Tensor,
                padding: torch.Tensor):
        """默认入口：返回生成序列与推动点下标。

        TorchScript 只把从 `forward` 可达的方法暴露给调用方；这里把生成作为默认
        入口，`generate` 另以 `@torch.jit.export` 显式暴露，两者共用同一份实现。
        """
        # 显式标注成 float，避免 TorchScript 把字面量 0.0 推成未知类型。
        greedy: float = 0.0
        tokens, push = self.generate(features, coords, padding, greedy)
        return tokens, push



def build_model(checkpoint_path: Path):
    """按补丁后的相对位置模块构造模型，使其可以被 TorchScript 编译。"""
    patched = load_patched_position()
    import training.model as model_module

    original = model_module.RelativeBias
    model_module.RelativeBias = patched.RelativeBias
    try:
        checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
        model = model_module.Generator(**checkpoint["config"])
        model.load_state_dict(checkpoint["model"])
        model.eval()
        exported = AndroidGenerator(model).eval()
    finally:
        model_module.RelativeBias = original
    return model, exported, checkpoint


def verify(model, scripted, tasks):
    """导出产物必须与原始 PyTorch 推理逐候选一致。

    贪心路径是确定的，因此直接比对生成结果本身；任何数值偏差都会在某个位置改变
    argmax，从而被这一步抓住。
    """
    from training.inference import generate as reference_generate

    for task in tasks:
        grid = positions(task)
        values, grid_tensor = condition(task, **model.feature_options)
        features = torch.zeros(1, len(grid), model.feature_count)
        coords = torch.zeros(1, len(grid), 3, dtype=torch.long)
        padding = torch.zeros(1, len(grid), dtype=torch.bool)
        features[0, : len(values)] = values
        coords[0, : len(grid_tensor)] = grid_tensor

        reference = reference_generate(model, [task], "cpu", temperature=0.0)[0]
        tokens, push = scripted.generate(features, coords, padding, 0.0)
        restored = decode_structure(task, tokens[0, : len(grid)].tolist(), int(push[0]))

        if reference["blocks"] != restored["blocks"] or reference["push"] != restored["push"]:
            raise SystemExit(
                f"导出产物与原始推理不一致（网格 {task['width']}×{task['height']}×"
                f"{task['depth']}）：方块 {len(reference['blocks'])} 对 "
                f"{len(restored['blocks'])}，推动点 {reference['push']} 对 {restored['push']}"
            )
    return len(tasks)


def verification_tasks(custom: Path | None):
    """一致性校验用的需求集合：覆盖不同截面尺寸与目标数量。"""
    if custom is not None:
        return [json.loads(custom.read_text())]
    return [
        # 单目标两格厚：最小可用形状。
        {"width": 2, "height": 2, "depth": 2, "max_ticks": 0, "rounds": 3,
         "load_blocks": 10, "targets": [{"x": 0, "y": 0, "z": 0, "order": 1}]},
        # 三目标两时序，三个截面列都有目标。
        {"width": 3, "height": 4, "depth": 3, "max_ticks": 0, "rounds": 3,
         "load_blocks": 10,
         "targets": [{"x": 0, "y": 0, "z": 0, "order": 1},
                     {"x": 1, "y": 1, "z": 0, "order": 1},
                     {"x": 2, "y": 2, "z": 0, "order": 2}]},
        # 五目标、更宽的截面，检验相对位置偏置在多列下的表现。
        {"width": 5, "height": 6, "depth": 4, "max_ticks": 0, "rounds": 3,
         "load_blocks": 10,
         "targets": [{"x": 0, "y": 0, "z": 0, "order": 1},
                     {"x": 1, "y": 2, "z": 0, "order": 1},
                     {"x": 2, "y": 4, "z": 0, "order": 2},
                     {"x": 3, "y": 1, "z": 0, "order": 2},
                     {"x": 4, "y": 5, "z": 0, "order": 3}]},
    ]


def main():
    parser = argparse.ArgumentParser(description="导出安卓端 TorchScript 模型")
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--task", type=Path, default=None,
                        help="追加一条自定义需求用于一致性校验")
    parser.add_argument("--threads", type=int, default=4, choices=range(1, 9),
                        help="导出校验的 CPU 线程数")
    options = parser.parse_args()
    torch.set_num_threads(options.threads)

    if not options.checkpoint.exists():
        raise SystemExit(f"未找到检查点：{options.checkpoint}")

    model, exported, checkpoint = build_model(options.checkpoint)
    with torch.inference_mode():
        scripted = torch.jit.script(exported)
    # `freeze` 会把图特化到常量折叠后的推理路径，提升移动端速度并减小体积，
    # 但它只保留 `forward`；安卓端还需要带温度参数的 `generate` 来支持超出八视角的
    # 采样候选，因此显式要求保留该入口。
    scripted = torch.jit.freeze(scripted.eval(), preserved_attrs=["generate"])
    if not hasattr(scripted, "generate"):
        raise SystemExit("导出后缺少 generate 入口，安卓端无法按温度采样")

    tasks = verification_tasks(options.task)
    with torch.inference_mode():
        checked = verify(model, scripted, tasks)

    options.output.mkdir(parents=True, exist_ok=True)
    model_path = options.output / f"{MODEL_STEM}.pt"
    # 必须用 `_save_for_lite_interpreter`，不能用 `scripted.save`。
    #
    # TorchScript 有两种互不兼容的序列化格式，都是合法归档、Python 侧都能加载，但
    # 成员构成不同：`save()` 写的是服务端格式（`data.pkl` + `code/`），Lite 解释器读的
    # 是移动端格式（`bytecode.pkl` + `constants.pkl`）。安卓侧用后者加载前一种文件时，
    # 报的是 `PytorchStreamReader failed locating file bytecode.pkl: file not found`。
    #
    # 这个错误极具误导性：它读起来像文件损坏或加载器装错，实际两边都正常，只是格式不对。
    # 而 `verify_apk_model.py` 用 `torch.jit.load` 验证——那恰恰是能读服务端格式的入口，
    # 所以验证会通过，问题只在真机上暴露。
    scripted._save_for_lite_interpreter(str(model_path))

    digest = hashlib.sha256(model_path.read_bytes()).hexdigest()
    config = checkpoint["config"]
    metadata = {
        "id": "combined-noz-relpos-12d-10.8m",
        "name": MODEL_STEM,
        "architecture": "autoregressive_v1",
        "inference": "cached_decoder_v1",
        "config": config,
        "parameters": int(sum(p.numel() for p in model.parameters())),
        "feature_columns": feature_count(
            use_target_z=config["use_target_z"],
            use_run_features=config["use_run_features"],
        ),
        "states": [[kind, facing] for kind, facing in STATES],
        "bos": BOS,
        "checkpoint_step": int(checkpoint.get("step", 0)),
        "torch_sha256": digest,
        "torch_version": torch.__version__,
        "verification_tasks": len(tasks),
    }
    (options.output / f"{MODEL_STEM}.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2)
    )

    size_mb = model_path.stat().st_size / 1024 / 1024
    print(f"已导出 {model_path}")
    print(f"体积 {size_mb:.1f} MiB，摘要 {digest[:16]}…")
    print(f"一致性校验通过：{checked} 条需求与原始推理逐候选一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
