"""从跨组闭环的真实供电接口继续原随机推拉树，增加后续时序。"""

from .geometry import add
from .power import sockets


def continuation(search, entry):
    """深层空接口接续到前层，不能在深层增设目标来制造时序。"""
    low = getattr(search.layout, 'output_low', None)
    if low is None:
        return dict(outputs=(1, 4), children=[])
    if entry[2] >= low:
        return dict(layer=low, outputs=(1, 4), children=[])
    from .layer_scheme import bands
    start = max(b['start'] for b in bands(search.depth) if b['start'] <= entry[2])
    next_entry = add(entry, (0, 0, 2))
    if next_entry[2] > search.layout.high:
        return None
    return dict(layer=start, outputs=(0, 0), relay_only=True, push_offset=0,
                children=[('push', continuation(search, next_entry))])


def grow(search, maximum=3):
    layout, rng = search.layout, search.rng
    attached = 0
    for _ in range(maximum):
        candidates = []
        for index, operation in enumerate(layout.operations):
            if not operation['charges']:
                continue
            observers = [p for p in operation['added']
                         if layout.blocks.get(p, {}).get('kind') == 'observer']
            for driver, kinds in sockets(layout.blocks, observers).items():
                if not layout.free(driver):
                    continue
                for kind in sorted(kinds):
                    entry = add(driver, (0, 0, -1 if kind == 'pull' else 2))
                    if layout.free(entry):
                        candidates.append((index, kind, driver, entry, operation['tick']))
        rng.shuffle(candidates)
        candidates.sort(key=lambda item: (item[1] != 'pull', -item[-1]))
        accepted = False
        for index, kind, driver, entry, tick in candidates[:32]:
            if search.simulations >= search.options.get('simulation_budget', 48):
                return attached
            saved = layout.checkpoint()
            layout.put(driver, 'sticky_piston' if kind == 'pull' else 'piston',
                       'negative_z' if kind == 'pull' else 'positive_z')
            layout.links.append(dict(kind=kind, driver=driver, entry=entry, tick=tick))
            child = continuation(search, entry)
            if child is None:
                layout.restore(saved)
                continue
            if search.extend(child, entry, tick+(8 if kind == 'pull' else 4)):
                layout.operations[index]['added'].append(driver)
                attached += 1
                accepted = True
                break
            layout.restore(saved)
        if not accepted:
            break
    return attached
