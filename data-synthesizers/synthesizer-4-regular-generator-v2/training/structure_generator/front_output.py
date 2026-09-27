"""将最终负载输出限定在前方两片，后层只能接力，不能后移目标规避距离。"""


def allowed(layout, piston):
    low = getattr(layout, 'output_low', None)
    return low is None or low <= piston[2] <= layout.high


def inspect(row):
    blocks = row['proposal']['blocks']
    if not blocks:
        return None, '没有可验证的前层输出'
    front = max(b['position']['z'] for b in blocks)
    targets = row['task']['targets']
    if not targets:
        return None, '没有前层目标'
    columns = {}
    for b in blocks:
        p = b['position']
        columns.setdefault((p['x'], p['y']), []).append(b)
    drivers = []
    for target in targets:
        if not front+1 <= target['z'] <= front+2:
            return None, '目标退入接力层，不能通过后移目标满足三格距离'
        behind = [b for b in columns.get((target['x'], target['y']), [])
                  if b['position']['z'] < target['z']]
        if not behind:
            return None, '目标列没有输出活塞'
        driver = max(behind, key=lambda b: b['position']['z'])
        if driver['block']['kind'] not in ('piston', 'sticky_piston') or driver['block']['facing'] != 'positive_z':
            return None, '目标列前端不是朝前输出活塞'
        if driver['position']['z'] < front-1:
            return None, '后层直接推动目标，缺少通向前层的接力'
        if row.get('construction', {}).get('layer_scheme'):
            from .layer_scheme import bands, owner
            if owner(row, driver['position']) != bands(row['task']['depth'])[-1]['start']:
                return None, '目标输出属于后层运动组，不能替代层间接力'
        if not 1 <= target['z']-driver['position']['z'] <= 3:
            return None, '输出活塞与目标点距离超过三格'
        drivers.append(driver['position'])
    return dict(body_front=front, output_depths=[front-1, front],
                target_depths=sorted({t['z'] for t in targets}), drivers=drivers), ''
