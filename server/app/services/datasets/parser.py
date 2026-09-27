from io import BytesIO
import math
import struct

import nbtlib

from .constants import MAX_AXIS, MAX_BLOCKS, MAX_VOLUME, MAX_FILE_BYTES
from .block_mapping import map_imported_block
from .block_facing import imported_block_facing
from .validation import validate_document


def parse_structure(content: bytes, filename: str):
    if not filename.lower().endswith(".mcstructure"):
        raise ValueError("请选择 .mcstructure 文件")
    if not content or len(content) > MAX_FILE_BYTES:
        raise ValueError("单个结构文件必须在 16 MiB 以内且不能为空")
    try:
        stream = BytesIO(content)
        root = nbtlib.File.parse(stream, byteorder="little")
        if stream.tell() != len(content) or int(root.get("format_version", 0)) != 1:
            raise ValueError("结构文件格式版本无效或包含多余数据")
        size = [int(n) for n in root["size"]]
        if len(size) != 3 or any(n < 1 or n > MAX_AXIS for n in size) or math.prod(size) > MAX_VOLUME:
            raise ValueError("结构尺寸过大：每轴最多 128 格，总体积最多 262144 格")
        structure = root["structure"]
        palette = []
        for entry in structure["palette"]["default"]["block_palette"]:
            name = str(entry["name"])
            states = {key: str(v) if isinstance(v, nbtlib.String) else float(v) if isinstance(v, (nbtlib.Float, nbtlib.Double)) else int(v) for key, v in entry.get("states", {}).items()}
            kind = map_imported_block(name)
            facing = imported_block_facing(kind, states)
            palette.append({"name": name, "states": states, "kind": kind, "facing": facing})
        layers = structure["block_indices"]
        if len(layers) != 2:
            raise ValueError("方块索引必须包含主层和附加层")
        blocks = []
        for layer, indices in enumerate(layers):
            if len(indices) != math.prod(size):
                raise ValueError("方块索引数量与结构尺寸不一致")
            for index, raw in enumerate(indices):
                palette_index = int(raw)
                if palette_index == -1:
                    continue
                if not 0 <= palette_index < len(palette):
                    raise ValueError("方块索引超出调色板范围")
                block = palette[palette_index]
                if block["name"] in ("minecraft:air", "minecraft:structure_void"):
                    continue
                blocks.append({**block, "layer": layer, "position": {"x": index // (size[1] * size[2]), "y": index // size[2] % size[1], "z": index % size[2]}})
                if len(blocks) > MAX_BLOCKS:
                    raise ValueError("单个移动线最多支持 4096 个非空气方块")
        return validate_document("samples", {
            "name": filename[:-12][:120] or "未命名移动线", "fileName": filename,
            "sourceSize": size, "sourceOrigin": [int(n) for n in root.get("structure_world_origin", [0, 0, 0])],
            "blocks": blocks, "forward": "positive_z", "pushPoint": None, "targets": [],
            "timing": None, "author": "", "notes": "", "completed": False,
        })
    except ValueError:
        raise
    except (KeyError, TypeError, IndexError, EOFError, AttributeError, OverflowError, struct.error, RecursionError) as error:
        raise ValueError("无法解析基岩版小端 NBT 结构文件，文件可能已损坏") from error
