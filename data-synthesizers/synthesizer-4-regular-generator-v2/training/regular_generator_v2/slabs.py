"""按行程与材料参数生成连续双排输出，不读取专家结构或旧单元库。"""


def slab(layout, left, width, z, material, order, flipped=False):
    """一个强充能位置带两个相邻目标；镜像后仍填满同一双排矩形。"""
    y = 1 if flipped else 0
    for x in range(left, left+width):
        layout.put(x, y, z, material)
        layout.put(x, 2 if flipped else -1, z, 'observer',
                   'negative_y' if flipped else 'positive_y')
        layout.output(x, y, z+1, order)
        layout.output(x, 1-y, z, order)


def scattered_output(layout, x, z, material, order, side=-1, flipped=False):
    """从端部横向连接后向外延伸，目标与双排核心至少隔开一行。"""
    y0 = 1 if flipped else 0
    direction = 1 if flipped else -1
    for step in range(3):
        layout.put(x+side, y0+direction*step, z, material)
    layout.put(x+side, y0+direction*3, z, 'observer',
               'negative_y' if flipped else 'positive_y')
    layout.output(x+side, y0+direction*2, z+1, order)
