"""用 Lite 解释器端到端验证权重，最接近真机的一层检查。

`verify_apk_model.py` 走 `torch.jit.load`，那是**服务端格式**的入口，因此它验证通过
并不能证明安卓读得动——两种 TorchScript 归档格式都是合法 ZIP，Python 侧都能加载，
差别只在成员构成（服务端用 `data.pkl`，Lite 用 `bytecode.pkl`）。这里改用
`torch._C._load_for_lite_interpreter`，与安卓端 `LiteModuleLoader` 走的是同一条读取与
执行路径，再逐候选比对参考推理。

三件事必须同时成立，缺一个都会在真机上表现为「模型加载失败」或「结果不对」：

1. 归档是 Lite 格式，Lite 解释器能反序列化；
2. `generate` 入口在 freeze 后仍然保留（`freeze` 默认只留 `forward`）；
3. padding 以 uint8（安卓侧 `Tensor.fromBlobUnsigned` 唯一能传的类型）传入时结果一致。

用法：

    .tools/training-venv/bin/python android/tools/lite_check.py \
        --model android/app/src/main/assets/oooi-scmls-v1.1-preview.pt \
        --checkpoint models/oooi-scmls-v1.1-preview.pt
"""

import argparse
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "android/tools"))

from training.data import condition  # noqa: E402
from training.inference import generate as reference_generate  # noqa: E402
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


def default_tasks():
    """覆盖最小截面、多目标与宽截面三种形状。"""
    return [
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


def main():
    parser = argparse.ArgumentParser(description="用 Lite 解释器验证安卓端权重")
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--checkpoint", required=True, type=Path)
    options = parser.parse_args()

    # 第二个参数在 2.6 上是占位（旧版是字节序标记），传 None 即可。
    lite = torch._C._load_for_lite_interpreter(str(options.model), None)
    methods = sorted(name for name in dir(lite) if not name.startswith("_"))
    print(f"Lite 解释器加载成功，可用方法：{methods}")
    if "run_method" not in methods:
        raise SystemExit("Lite 模块缺少 run_method，无法调用具名入口")

    model = load_reference(options.checkpoint)
    failures = []
    for index, task in enumerate(default_tasks()):
        grid = positions(task)
        values, grid_tensor = condition(task, **model.feature_options)
        features = torch.zeros(1, len(grid), model.feature_count)
        coords = torch.zeros(1, len(grid), 3, dtype=torch.long)
        features[0, : len(values)] = values
        coords[0, : len(grid_tensor)] = grid_tensor
        reference = reference_generate(model, [task], "cpu", temperature=0.0)[0]

        size = f"{task['width']}×{task['height']}×{task['depth']}"
        for label, dtype in (("bool", torch.bool), ("uint8", torch.uint8)):
            padding = torch.zeros(1, len(grid), dtype=dtype)
            try:
                # run_method 只接受一个元组，不能按位置展开。
                output = lite.run_method("generate", (features, coords, padding, 0.0))
                tokens = output[0][0, : len(grid)].tolist()
                push = int(output[1][0])
                restored = decode_structure(task, tokens, push)
                same = (restored["blocks"] == reference["blocks"]
                        and restored["push"] == reference["push"])
                print(f"[{index}] {size} padding={label}：{'一致' if same else '不一致'}"
                      f"（方块 {len(restored['blocks'])} 对 {len(reference['blocks'])}）")
                if not same:
                    failures.append(f"{size} padding={label}")
            except Exception as error:  # noqa: BLE001 - 把底层报错原样带给使用者
                print(f"[{index}] {size} padding={label}：抛异常 {type(error).__name__}: {error}")
                failures.append(f"{size} padding={label}：{type(error).__name__}")

    if failures:
        print("\n存在问题：")
        for item in failures:
            print(f"  - {item}")
        raise SystemExit(1)
    print("\nLite 解释器端到端一致：与安卓端同一条读取与执行路径，结果与参考推理相同")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
