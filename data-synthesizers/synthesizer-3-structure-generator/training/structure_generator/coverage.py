"""以真实截面统计密度、目标邻接与尺寸覆盖。"""


def describe(row):
    task = row['task']
    targets = {(t['x'],t['y']) for t in task['targets']}
    neighboring = sum(any((x+dx,y+dy) in targets for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)))
                      for x,y in targets)
    return dict(category=row['family'],actual_depth=task['depth'],width=task['width'],height=task['height'],
                targets=len(task['targets']),groups=len({t['order'] for t in task['targets']}),
                density=round(len(task['targets'])/(task['width']*task['height']),4),
                adjacent_target_fraction=round(neighboring/max(1,len(targets)),4),
                blocks=len(row['proposal']['blocks']))


def trim_bounds(row):
    """删除冗余后收紧横截面，并同步本体、目标与机制元数据坐标。"""
    blocks = row['proposal']['blocks']
    offset = {a:min(b['position'][a] for b in blocks) for a in ('x','y')}
    def shift(value):
        if isinstance(value,dict):
            if all(a in value for a in ('x','y','z')):
                return {**value,**{a:value[a]-d for a,d in offset.items()}}
            return {k:shift(v) for k,v in value.items()}
        if isinstance(value,list):
            return [shift(v) for v in value]
        return value
    for key in ('task','proposal','construction','mechanisms'):
        row[key] = shift(row[key])
    for axis,label in (('x','width'),('y','height')):
        row['task'][label] = max(b['position'][axis] for b in row['proposal']['blocks'])+1
    row['coverage'] = describe(row)
