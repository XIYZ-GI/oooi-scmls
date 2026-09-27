"""验证打包进 APK 的 TorchScript 权重。

导出时的一致性校验用的是内存里刚构造的模块，无法证明**磁盘上那个文件**加载后行为
不变；而 `.pt` 在打包前还要经过一次落盘与拷入 assets。这个脚本直接 `torch.jit.load`
权重文件本体，逐候选与参考推理比对，覆盖三件事：

1. 落盘后的 `.pt` 仍是完整的、能被 TorchScript 反序列化的模块（freeze 后 `generate`
   是否真的被保留）。
2. 贪心路径与 `training.inference.generate` 完全一致——数值偏差会在某个位置改变
   argmax，从而被抓住。
3. padding 用 uint8 而非 bool 传入时行为是否一致。安卓侧 `Tensor.fromBlobUnsigned`
   只能传字节，TorchScript 收到的是 uint8 张量而非 bool；masked_fill 在两种 dtype 下
   语义未必相同，所以必须实测，不能靠推断。
4. 归档是不是 **Lite 格式**。`torch.jit.load` 能读服务端格式，因此它验证通过并不能说明
   安卓的 Lite 解释器读得动；两种格式都是合法归档，只有成员构成不同。这里直接查归档
   成员，缺 `bytecode.pkl` 就报错——否则问题会一路留到真机才炸。
"""

import argparse
import json
import sys
import zipfile
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from training.data import condition  # noqa: E402
from training.inference import generate as reference_generate  # noqa: E402
from training.model import Generator  # noqa: E402
from training.serialization import decode_structure, positions  # noqa: E402


def load_reference(checkpoint_path: Path):
    """按导出脚本的同款修补加载原始检查点。"""
    from position_patch import load_patched_position

    import training.model as model_module

    original = model_module.RelativeBias
    model_module.RelativeBias = load_patched_position().RelativeBias
    try:
        checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
        model = model_module.Generator(**checkpoint["config"])
        model.load_state_dict(checkpoint["model"])
        model.eval()
    finally:
        model_module.RelativeBias = original
    return model


def inputs_for(model, task):
    """构造与安卓侧 `Inference.build` 同形的三份输入。"""
    grid = positions(task)
    values, grid_tensor = condition(task, **model.feature_options)
    features = torch.zeros(1, len(grid), model.feature_count)
    coords = torch.zeros(1, len(grid), 3, dtype=torch.long)
    features[0, : len(values)] = values
    coords[0, : len(grid_tensor)] = grid_tensor
    return grid, features, coords


def run(scripted, grid, features, coords, padding):
    """走 `generate` 导出入口；返回解码后的结构与推动点。"""
    tokens, push = scripted.generate(features, coords, padding, 0.0)
    return tokens[0, : len(grid)].tolist(), int(push[0])


def main():
    parser = argparse.ArgumentParser(description="验证 APK 内 TorchScript 权重")
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--tasks", type=Path)
    args = parser.parse_args()

    # 先查格式：`torch.jit.load` 两种格式都能读，所以下载入成功不构成证据。
    with zipfile.ZipFile(args.model) as archive:
        members = archive.namelist()
    if not any(name.endswith("bytecode.pkl") for name in members):
        raise SystemExit(
            f"{args.model.name} 不是 Lite 格式：归档里没有 bytecode.pkl。\n"
            "导出时用了 `scripted.save()`，安卓的 Lite 解释器读不了这种服务端格式，"
            "必须改用 `scripted._save_for_lite_interpreter()`。"
        )
    print(f"归档格式：Lite（含 bytecode.pkl，共 {len(members)} 个成员）")

    scripted = torch.jit.load(str(args.model), map_location="cpu").eval()
    print(f"已加载 {args.model.name}（{args.model.stat().st_size / 1048576:.1f} MiB）")
    has_generate = hasattr(scripted, "generate")
    print(f"冻结后仍暴露 generate：{has_generate}")

    model = load_reference(args.checkpoint)
    tasks = json.loads(args.tasks.read_text()) if args.tasks else [
        {"width": 2, "height": 2, "depth": 2, "max_ticks": 0, "rounds": 3, "load_blocks": 10,
         "targets": [{"x": 0, "y": 0, "z": 0, "order": 1}]},
        {"width": 3, "height": 4, "depth": 3, "max_ticks": 0, "rounds": 3, "load_blocks": 10,
         "targets": [{"x": 0, "y": 0, "z": 0, "order": 1}, {"x": 1, "y": 1, "z": 0, "order": 1},
                     {"x": 2, "y": 2, "z": 0, "order": 2}]},
        {"width": 5, "height": 6, "depth": 4, "max_ticks": 0, "rounds": 3, "load_blocks": 10,
         "targets": [{"x": 0, "y": 0, "z": 0, "order": 1}, {"x": 2, "y": 1, "z": 0, "order": 1},
                     {"x": 4, "y": 5, "z": 0, "order": 2}, {"x": 1, "y": 4, "z": 0, "order": 2},
                     {"x": 3, "y": 2, "z": 0, "order": 3}]},
    ]

    failures = []
    for index, task in enumerate(tasks):
        size = f"{task['width']}×{task['height']}×{task['depth']}"
        grid, features, coords = inputs_for(model, task)
        bool_padding = torch.zeros(1, len(grid), dtype=torch.bool)
        # 安卓侧只能传字节：uint8 的 0 与 bool 的 false 在内存里同形。
        uint8_padding = torch.zeros(1, len(grid), dtype=torch.uint8)

        reference = reference_generate(model, [task], "cpu", temperature=0.0)[0]
        reference_blocks = reference["blocks"]

        for label, padding in (("bool", bool_padding), ("uint8", uint8_padding)):
            try:
                tokens, push = run(scripted, grid, features, coords, padding)
                restored = decode_structure(task, tokens, push)
                same = restored["blocks"] == reference_blocks and restored["push"] == reference["push"]
                print(f"[{index}] {size} padding={label}：{'一致' if same else '不一致'}"
                      f"（方块 {len(restored['blocks'])} 对 {len(reference_blocks)}）")
                if not same:
                    failures.append(f"{size} padding={label}")
            except Exception as error:  # noqa: BLE001 - 要把底层报错原样带给使用者
                print(f"[{index}] {size} padding={label}：抛异常 {type(error).__name__}: {error}")
                failures.append(f"{size} padding={label}：{type(error).__name__}")

    if failures:
        print("\n存在问题：")
        for item in failures:
            print(f"  - {item}")
        raise SystemExit(1)
    print(f"\n全部一致：{len(tasks)} 条需求，两种 padding dtype 都与参考推理相同")


if __name__ == "__main__":
    main()
