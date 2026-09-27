"""为随机拉驱的驱动列补充前向观察者输出，逐列保持三格内距离。"""

from .geometry import add
from .front_output import allowed as output_allowed


def grow(search):
    layout, rng = search.layout, search.rng
    candidates = [(link['driver'], link['tick']) for link in layout.links if 'tick' in link]
    rng.shuffle(candidates)
    count = 0
    for driver, tick in candidates:
        if len(layout.outputs) >= 32 or any(v['piston'][:2] == driver[:2] for v in layout.outputs):
            continue
        observer, output = add(driver, (0, 0, 1)), add(driver, (0, 0, 2))
        if not output_allowed(layout, output):
            continue
        saved = layout.checkpoint()
        if not layout.put(observer, 'observer'):
            continue
        if not layout.put(output, 'piston'):
            layout.restore(saved)
            continue
        layout.outputs.append(dict(piston=output, tick=tick+4))
        if search.valid():
            count += 1
        else:
            layout.restore(saved)
    return count
