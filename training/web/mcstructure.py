"""把生成候选的方块写成基岩版小端 NBT 的 .mcstructure 结构。

方块名与方块状态的映射和 `server/app/services/datasets` 的导入规则互为反向：
活塞使用活塞专用的朝向编号，观察者的引擎朝向表示输出端，写回方块状态时要反回到观察端。
"""

import io

import nbtlib

# 引擎方块类型 → 基岩版方块名。
BLOCK_NAMES = {
    'slime_block': 'minecraft:slime',
    'honey_block': 'minecraft:honey_block',
    'piston': 'minecraft:piston',
    'sticky_piston': 'minecraft:sticky_piston',
    'redstone_block': 'minecraft:redstone_block',
    'observer': 'minecraft:observer',
    'iron_block': 'minecraft:iron_block',
    'light_blue_glazed_terracotta': 'minecraft:light_blue_glazed_terracotta',
    'glass': 'minecraft:glass',
}
# 方块状态的朝向编号顺序；活塞与其它方块不同。
DIRECTIONS = ('negative_y', 'positive_y', 'negative_z', 'positive_z', 'negative_x', 'positive_x')
PISTON_DIRECTIONS = ('negative_y', 'positive_y', 'positive_z', 'negative_z', 'positive_x', 'negative_x')
DIRECTED_KINDS = ('piston', 'sticky_piston', 'observer', 'light_blue_glazed_terracotta')
# 真实结构文件里每个调色板条目都带方块状态版本，读取端不使用，这里按基岩版当前值写入。
BLOCK_VERSION = 17959425


def opposite(facing):
    """返回相反方向，例如 positive_z 的对侧是 negative_z。"""
    side = 'negative' if facing.startswith('positive') else 'positive'
    return side + facing[facing.index('_'):]


def facing_value(kind, facing):
    """引擎朝向 → 方块状态 facing_direction 的编号。"""
    table = PISTON_DIRECTIONS if kind in ('piston', 'sticky_piston') else DIRECTIONS
    value = opposite(facing) if kind == 'observer' else facing
    if value not in table:
        raise ValueError(f'{kind} 的朝向无法写入结构：{facing}')
    return table.index(value)


def palette_entry(kind, facing):
    name = BLOCK_NAMES.get(kind)
    if name is None:
        raise ValueError(f'暂不支持导出这种方块：{kind}')
    states = nbtlib.Compound()
    if kind in DIRECTED_KINDS:
        states['facing_direction'] = nbtlib.Int(facing_value(kind, facing))
    return nbtlib.Compound({'name': nbtlib.String(name), 'states': states, 'version': nbtlib.Int(BLOCK_VERSION)})


def structure_bytes(blocks):
    """blocks 为 `{position:{x,y,z}, block:{kind,facing}}` 列表，返回 .mcstructure 二进制内容。"""
    if not blocks:
        raise ValueError('这个候选没有可以导出的方块')
    positions = [block['position'] for block in blocks]
    low = {axis: min(position[axis] for position in positions) for axis in 'xyz'}
    size = {axis: max(position[axis] for position in positions) - low[axis] + 1 for axis in 'xyz'}
    # 方块索引按 x*(高*厚) + y*厚 + z 排列；负坐标通过原点偏移记录，索引本身始终非负。
    indices = [-1] * (size['x'] * size['y'] * size['z'])
    palette, entries = {}, []
    for block in blocks:
        value = block['block']
        key = (value['kind'], value['facing'])
        if key not in palette:
            palette[key] = len(entries)
            entries.append(palette_entry(*key))
        position = block['position']
        indices[(position['x'] - low['x']) * size['y'] * size['z']
                + (position['y'] - low['y']) * size['z'] + position['z'] - low['z']] = palette[key]
    empty = [-1] * len(indices)
    root = nbtlib.File({
        'format_version': nbtlib.Int(1),
        'size': nbtlib.List[nbtlib.Int]([nbtlib.Int(size[axis]) for axis in 'xyz']),
        'structure_world_origin': nbtlib.List[nbtlib.Int]([nbtlib.Int(low[axis]) for axis in 'xyz']),
        'structure': nbtlib.Compound({
            'block_indices': nbtlib.List[nbtlib.List[nbtlib.Int]]([
                nbtlib.List[nbtlib.Int]([nbtlib.Int(index) for index in indices]),
                nbtlib.List[nbtlib.Int]([nbtlib.Int(index) for index in empty]),
            ]),
            'entities': nbtlib.List[nbtlib.Compound]([]),
            'palette': nbtlib.Compound({'default': nbtlib.Compound({
                'block_palette': nbtlib.List[nbtlib.Compound](entries),
                'block_position_data': nbtlib.Compound(),
            })}),
        }),
    }, byteorder='little')
    buffer = io.BytesIO()
    # write 的 byteorder 默认是大端，基岩版结构必须显式写小端。
    root.write(buffer, byteorder='little')
    return buffer.getvalue()
