"""从空布局进行方块级生长，遇到占位或功能冲突时回退局部编辑。"""

from ..domain_rules import proposal_issues
from .config import LIMITS, MATERIALS, SIDES, VERSION
from .geometry import add, point, position
from .growth import supply
from .layout import Layout
from .power import sockets
from .requests import requirements


def connected(blocks, anchor):
    """检查本次编辑形成的方块能否由入口沿前进方向带动。"""
    queue, visited = [anchor], set()
    while queue:
        p = queue.pop()
        if p in visited or p not in blocks:
            continue
        visited.add(p)
        queue.append(add(p, (0, 0, 1)))
        if blocks[p]['kind'] in MATERIALS:
            for d in (*SIDES, (0, 0, 1), (0, 0, -1)):
                q = add(p, d)
                other = blocks.get(q, {}).get('kind')
                if (other and other != 'light_blue_glazed_terracotta'
                        and {blocks[p]['kind'], other} != set(MATERIALS)):
                    queue.append(q)
    return len(visited) == len(blocks) <= 12


def extend(layout, rng, request, anchor, tick, depth, budget, root=False):
    checkpoint = layout.checkpoint()
    for _ in range(18):
        budget[0] -= 1
        if budget[0] < 0:
            break
        layout.restore(checkpoint)
        styles = ['共享供电片', '前置供电', '入口延伸']
        if root and depth == 4:
            styles = ['共享供电片', '前置供电']
        if root and depth in (2, 3) and request['children'][0:1] and request['children'][0][0] == 'pull':
            styles = ['入口延伸', '入口延伸', '前置供电', '共享供电片']
        added = supply(layout, rng, anchor, rng.choice(styles), budget=8)
        if not added:
            continue
        available = sockets(layout.blocks, added)
        links, used = [], set()
        valid = True
        for kind, child in request['children']:
            options = [p for p, kinds in available.items() if kind in kinds and p not in used
                       and layout.free(p) and layout.free(add(p, (0, 0, -1 if kind == 'pull' else 2)))]
            rng.shuffle(options)
            if root and kind == 'pull':
                preferred = 1 if depth == 2 else 0
                options.sort(key=lambda p: abs(p[2]-preferred))
            if not options:
                valid = False
                break
            p = options[0]
            layout.put(p, 'sticky_piston' if kind == 'pull' else 'piston',
                       'negative_z' if kind == 'pull' else 'positive_z')
            added.add(p)
            used.add(p)
            entry = add(p, (0, 0, -1 if kind == 'pull' else 2))
            links.append((kind, child, p, entry))
        if not valid:
            continue
        outputs = [p for p, kinds in available.items() if 'push' in kinds and p not in used
                   and layout.free(p) and p[:2] not in {v['piston'][:2] for v in layout.outputs}
                   and not any(q[:2] == p[:2] and q[2] > p[2] for q in layout.blocks)]
        rng.shuffle(outputs)
        low, high = request['outputs']
        high = min(high, len(outputs), 12-len(added))
        if high < low:
            continue
        count = rng.randint(low, high)
        if rng.random() < .45:
            count = high
        selected = []
        for p in outputs:
            if len(selected) >= count:
                break
            if p[:2] in {q[:2] for q in selected}:
                continue
            selected.append(p)
            layout.put(p, 'piston', 'positive_z')
            added.add(p)
            layout.outputs.append(dict(piston=p, tick=tick+4))
        if len(selected) < low or not connected({p: layout.blocks[p] for p in added}, anchor):
            continue
        if proposal_issues(dict(blocks=layout.payload(), push=position((0, 0, 0)))):
            continue
        success = True
        for kind, child, driver, entry in links:
            layout.links.append(dict(kind=kind, driver=driver, entry=entry))
            if not extend(layout, rng, child, entry, tick+(8 if kind == 'pull' else 4),
                          depth, budget):
                success = False
                break
        if success:
            return True
    layout.restore(checkpoint)
    return False


def construct(rng, category, depth, dense=False):
    if depth == 3 and category != '多目标同推':
        low, high = -1, 1
    else:
        low, high = 0, depth-1
    layout = Layout(low, high)
    request = requirements(rng, category, depth, dense)
    budget = [220]
    if not extend(layout, rng, request, (0, 0, 0), 4, depth, budget, root=True):
        return None, '有界布局搜索未找到连接'
    outputs = layout.outputs
    if len(outputs) < 3:
        return None, '有效输出不足三个'
    if len(outputs) > LIMITS['targets']:
        return None, '超出目标数量预算'
    if any(any(q[:2] == p['piston'][:2] and q[2] > p['piston'][2] for q in layout.blocks)
           for p in outputs):
        return None, '后续编辑占用了输出负载列'
    actual_depth = max(p[2] for p in layout.blocks)-min(p[2] for p in layout.blocks)+1
    if actual_depth != depth:
        return None, '实际厚度未达到请求值'
    offset = (min(p[0] for p in layout.blocks), min(p[1] for p in layout.blocks),
              max(p[2] for p in layout.blocks)+2)
    shift = lambda p: position(add(p, offset, -1))
    ranks = {t: i+1 for i, t in enumerate(sorted({v['tick'] for v in outputs}))}
    targets = [{**shift(add(v['piston'], (0, 0, 2))), 'order': ranks[v['tick']]} for v in outputs]
    blocks = [dict(position=shift(p), block=dict(b)) for p, b in sorted(layout.blocks.items())]
    width = max(b['position']['x'] for b in blocks)+1
    height = max(b['position']['y'] for b in blocks)+1
    if width > LIMITS['width'] or height > LIMITS['height'] or width*height*depth > LIMITS['volume']:
        return None, '超出空间预算'
    task = dict(width=width, height=height, depth=depth, targets=sorted(targets, key=point),
                max_ticks=max(48, max(v['tick'] for v in outputs)+12), rounds=3, load_blocks=10)
    links = [{**v, 'driver': shift(v['driver']), 'entry': shift(v['entry'])} for v in layout.links]
    operations = [{**v, 'anchor': shift(v['anchor']), 'charges': [shift(p) for p in v['charges']],
                   'added': [shift(p) for p in v['added']]} for v in layout.operations]
    row = dict(task=task, proposal=dict(blocks=blocks, push=shift((0, 0, 0))),
               construction=dict(links=links, operations=operations, steps=220-budget[0]),
               source=VERSION, family=category)
    return row, ''
