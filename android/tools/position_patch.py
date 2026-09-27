"""让解码器的相对位置模块可以被 TorchScript 脚本化。

问题：`training/position.py` 的 `RelativeBias.forward` 直接使用模块级常量 `MAX_OFFSET`，
而 TorchScript 不接受闭包捕获的全局 `int`（报 “python value of type 'int' cannot be used
as a value”）。该常量只被这个文件自己使用，`training/` 下的其他代码和测试都只引用
`LEVELS`、`MAGNITUDE_LEVELS` 与 `RelativeBias` 本身。

关键细节：**TorchScript 用 `inspect.getsource` 从磁盘上的真实文件读源码来编译**，
`__file__` 指向哪个文件它就重新读哪份原文。因此仅仅 `exec` 一份改过的文本没有用，
补丁后的源码必须落成一个真实文件再导入。

做法：不修改 `training/` 的生产代码，把源码里的常量替换成等值字面量后写到导出目录下的
真实模块文件，再从那里导入。替换逐处可控、数值与原文完全一致，因此不存在两份实现——
只有同一份源码的文字替换。替换结果由 `export_model.py` 的数值一致性校验兜底。
"""

import importlib.util
from pathlib import Path

POSITION_SOURCE = Path(__file__).resolve().parents[2] / "training" / "position.py"
PATCH_DIR = Path(__file__).resolve().parents[1] / "build" / "patched"
PATCHED_FILE = PATCH_DIR / "patched_position.py"

# 需要内联成字面量的模块级常量。这些是 TorchScript 不接受的闭包全局量。
INLINE_CONSTANTS = {
    "MAX_OFFSET": 32,
    "LEVELS": 9,
}


def _patched_source() -> str:
    """把常量替换成字面量后的源码文本。"""
    text = POSITION_SOURCE.read_text(encoding="utf-8")
    for name, value in INLINE_CONSTANTS.items():
        # 赋值语句本身保留为同名常量，便于阅读；真正需要内联的是使用处。
        text = text.replace(f"clamp(max={name})", f"clamp(max={value})")
        text = text.replace(f"nn.Embedding({name}, heads)", f"nn.Embedding({value}, heads)")
    # 保住常量定义本身，供模块内的其余引用使用。
    return text


def load_patched_position():
    """把补丁源码写成真实文件后导入，返回可直接脚本化的 `position` 模块。"""
    PATCH_DIR.mkdir(parents=True, exist_ok=True)
    text = _patched_source()

    # 只在内容变化时重写，避免无谓地使 TorchScript 缓存失效。
    if not PATCHED_FILE.exists() or PATCHED_FILE.read_text(encoding="utf-8") != text:
        PATCHED_FILE.write_text(text, encoding="utf-8")

    spec = importlib.util.spec_from_file_location("patched_position", PATCHED_FILE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法从 {PATCHED_FILE} 构造模块")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "RelativeBias"):
        raise RuntimeError("补丁后的 position 模块缺少 RelativeBias")
    return module
