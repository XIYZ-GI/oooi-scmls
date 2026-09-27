"""推驱优化结构模板：推驱扇出、拉驱接力、多级级联三种思路的参数化实现。

规范坐标系约定：前进方向为 +z，横截面为 x/y，输出活塞一律朝 +z。

* 推驱中心：观察者 + 强充能方块 + 与该方块六邻接的活塞。观察者随所在组
  被推进到位后立即脉冲，强充能方块因此在同一刻给一组活塞供电，同层活塞
  同刻伸出——这是“多目标点同时推驱”的来源。
* 推驱扇出：上一层活塞推动下一层推驱中心的入口块，下一层中心数量可以
  多于上一层，最后一层所有活塞同时推目标。
* 拉驱接力：粘性活塞钩住下一组的入口块，随本组前进一格把它带前，回缩时
  再把多推出去的一格拉回来，使下一组恰好前进一格并触发它的观察者。
* 多级级联：把上述两种接力串成多级，各级在不同游戏刻被触发，形成多时序。
"""

import random

from .frame import LATERAL, MATERIALS, SIDE_FACING, Frame


def _free_lateral(frame, cell):
    return [(cell[0]+d[0], cell[1]+d[1], cell[2])
            for d in LATERAL if frame.free((cell[0]+d[0], cell[1]+d[1], cell[2]))]


def compact_hub(rng, frame, cell, max_pistons=4, reserve=0, avoid=()):
    """入口块本身成为强充能块；观察者侧贴，活塞与强充能块同层。"""
    if not frame.free(cell) or not frame.put(cell, frame.material):
        return None
    sides = [c for c in _free_lateral(frame, cell) if c not in avoid]
    if not sides:
        return None
    rng.shuffle(sides)
    observer = sides[0]
    facing = SIDE_FACING[(cell[0]-observer[0], cell[1]-observer[1])]
    if not frame.put(observer, 'observer', facing):
        return None
    hub = frame.add_hub(cell, observer, 'compact')
    slots = [c for c in _free_lateral(frame, cell) if c not in avoid]
    rng.shuffle(slots)
    count = rng.randint(1, max(1, min(max_pistons, len(slots)-reserve)))
    for slot in slots[:count]:
        if frame.piston(slot):
            hub['pistons'].append(slot)
    return hub


def expanded_hub(rng, frame, cell, max_pistons=4, avoid=()):
    """入口块与观察者同层，强充能块位于观察者输出端的前一层。"""
    if not frame.free(cell) or not frame.put(cell, frame.material):
        return None
    sides = [c for c in _free_lateral(frame, cell) if c not in avoid]
    if not sides:
        return None
    rng.shuffle(sides)
    observer = sides[0]
    charge = (observer[0], observer[1], observer[2]+1)
    if not frame.put(observer, 'observer', 'positive_z'):
        return None
    if not frame.free(charge) or not frame.put(charge, frame.material):
        return None
    hub = frame.add_hub(charge, observer, 'expanded')
    slots = _free_lateral(frame, charge)
    front = (charge[0], charge[1], charge[2]+1)
    if max_pistons >= 5 and frame.free(front):
        slots.append(front)
    rng.shuffle(slots)
    for slot in slots[:max_pistons]:
        if frame.piston(slot):
            hub['pistons'].append(slot)
    return hub


def root_stage(rng, frame, hubs, spacing, max_pistons=3, reserve=0):
    """离合层：外部活塞只推其中一个强充能块，整层靠黏附一起前进。"""
    xs = [i*spacing for i in range(hubs)]
    for index, x in enumerate(xs):
        if index:
            for gap in range(xs[index-1]+1, x):
                frame.put((gap, 0, 0), frame.material)
    stage = dict(level=0, hubs=[], pistons=[])
    for x in xs:
        hub = compact_hub(rng, frame, (x, 0, 0), max_pistons, reserve if x == xs[0] else 0)
        if hub is None or not hub['pistons']:
            return None
        stage['hubs'].append(hub)
        stage['pistons'].extend(hub['pistons'])
    frame.stages.append(stage)
    return stage, (xs[0], 0, 0)


def relay_stage(rng, frame, relays, level, expanded_ratio, per_hub):
    """上一层活塞各推一个入口块，形成**彼此独立**的推驱中心。

    中心用侧贴观察者（同层、输出端正对入口块），中心之间不黏附相连：
    不连接也能被正确推动，连起来只会白白多耗方块。expanded_ratio 只在
    需要额外一层（复杂目标/多时序）时才用得上。
    """
    stage = dict(level=level, hubs=[], pistons=[])
    for relay in relays:
        cell = (relay[0], relay[1], relay[2]+2)
        builder = expanded_hub if rng.random() < expanded_ratio else compact_hub
        hub = builder(rng, frame, cell, per_hub)
        if hub is None or not hub['pistons']:
            continue
        stage['hubs'].append(hub)
        stage['pistons'].extend(hub['pistons'])
    if not stage['hubs']:
        return None
    frame.stages.append(stage)
    return stage


def band_stage(rng, frame, relays, level, max_pistons):
    """第二层＝相连的输入带 + 相连的强充能带，多个强充能块各自配观察者。

    输入带被上一层活塞推动整带前进；强充能带与输入带黏附相连，因此同层可以
    出现多个强充能块（每块一个观察者），观察者可以侧贴（同层）也可以在后一层
    正对，活塞只取部分侧位、允许留空。整条带 ≥ 两格厚，配合离合层就是四格。
    """
    ys = {relay[1] for relay in relays}
    if len(ys) != 1:
        return None
    y = relays[0][1]
    z = relays[0][2] + 2
    pushed = {(relay[0], relay[1]) for relay in relays}
    xs = sorted({relay[0] for relay in relays})
    low, high = xs[0]-1, xs[-1]+1
    if high-low < 1:
        return None
    for x in range(low, high+1):
        if not frame.free((x, y, z)):
            return None
        frame.put((x, y, z), frame.material)
        frame.put((x, y, z+1), frame.material)
    stage = dict(level=level, hubs=[], pistons=[])
    columns = [x for x in range(low, high+1)]
    rng.shuffle(columns)
    bands = []
    for x in columns:
        if len(bands) >= rng.choice((2, 2, 3, 3, 4)) or len(bands) >= len(columns):
            break
        charge = (x, y, z+1)
        if frame.blocks.get(charge, {}).get('kind') not in MATERIALS:
            continue
        styles = []
        if (x, y) not in pushed:
            styles.append('behind')
        styles.append('side')
        for style in styles:
            if style == 'behind':
                entry_cell = (x, y, z)
                if not frame.free(entry_cell) and frame.blocks.get(entry_cell, {}).get('kind') not in MATERIALS:
                    continue
                frame.blocks.pop(entry_cell, None)
                if not frame.put(entry_cell, 'observer', 'positive_z'):
                    continue
                hub = frame.add_hub(charge, entry_cell, 'behind')
            else:
                sides = [c for c in _free_lateral(frame, charge) if c[2] == z+1]
                if not sides:
                    continue
                rng.shuffle(sides)
                observer = sides[0]
                facing = SIDE_FACING[(charge[0]-observer[0], charge[1]-observer[1])]
                if not frame.put(observer, 'observer', facing):
                    continue
                hub = frame.add_hub(charge, observer, 'side')
            if hub is None:
                continue
            slots = [c for c in _free_lateral(frame, charge)
                     if c[2] == z+1 or c == (charge[0], charge[1], charge[2]+1)]
            rng.shuffle(slots)
            count = rng.randint(1, max(1, min(max_pistons, len(slots))))
            for slot in slots[:count]:
                if frame.piston(slot):
                    hub['pistons'].append(slot)
            if hub['pistons']:
                stage['hubs'].append(hub)
                stage['pistons'].extend(hub['pistons'])
                bands.append(hub)
                break
    if not stage['hubs']:
        return None
    frame.stages.append(stage)
    return stage


def hook_unit(rng, frame, charge, max_pistons=3, avoid=()):
    """已验证的拉驱接力单元：粘性活塞朝后，把后方整组粘液块拉前一格。

    粘性活塞挂在强充能块侧边（与推驱同刻被激活），它后方一格正好是被拉
    推驱中心的强充能块；活塞回缩时把该中心整组拉进一格，随后该中心组脉冲、
    同刻推出自己的全部目标。
    """
    slots = _free_lateral(frame, charge)
    rng.shuffle(slots)
    for slot in slots:
        cell = (slot[0], slot[1], slot[2]-1)
        if not frame.free(cell):
            continue
        if not frame.put(slot, 'sticky_piston', 'negative_z'):
            continue
        entry = compact_hub(rng, frame, cell, max_pistons, 0, avoid)
        if entry is None or not entry['pistons']:
            continue
        frame.sticky.append(slot)
        return entry
    return None


def hook_stage(rng, frame, charges, level, per_hub):
    """拉驱接力：粘性活塞在强充能块正前方，入口块正好位于它伸出的一格。"""
    stage = dict(level=level, hubs=[], pistons=[], hooks=[])
    for charge in charges:
        sticky = (charge[0], charge[1], charge[2]+1)
        cell = (charge[0], charge[1], charge[2]+2)
        if not frame.free(sticky) or not frame.put(sticky, 'sticky_piston', 'positive_z'):
            continue
        hub = compact_hub(rng, frame, cell, per_hub)
        if hub is None or not hub['pistons']:
            continue
        stage['hubs'].append(hub)
        stage['pistons'].extend(hub['pistons'])
        stage['hooks'].append(sticky)
    if not stage['hubs']:
        return None
    frame.stages.append(stage)
    return stage


def _add_some(frame, stage, limit):
    added = 0
    for piston in stage['pistons']:
        if added >= limit:
            break
        if frame.add_target(piston, stage['level']):
            added += 1
    return added


def add_loads(frame, stage, limit):
    return _add_some(frame, stage, limit)


def band_stage(rng, frame, relays, level, max_pistons):
    """第二层＝相连的输入带 + 相连的强充能带，多个强充能块各自配观察者。

    输入带被上一层活塞推动整带前进；强充能带与输入带黏附相连，因此同层可以
    出现多个强充能块（每块一个观察者），观察者可以侧贴（同层）也可以在后一层
    正对，活塞只取部分侧位、允许留空。整条带 ≥ 两格厚，配合离合层就是四格。
    """
    ys = {relay[1] for relay in relays}
    if len(ys) != 1:
        return None
    y = relays[0][1]
    z = relays[0][2] + 2
    pushed = {(relay[0], relay[1]) for relay in relays}
    xs = sorted({relay[0] for relay in relays})
    low, high = xs[0]-1, xs[-1]+1
    if high-low < 1:
        return None
    for x in range(low, high+1):
        if not frame.free((x, y, z)):
            return None
        frame.put((x, y, z), frame.material)
        frame.put((x, y, z+1), frame.material)
    stage = dict(level=level, hubs=[], pistons=[])
    columns = [x for x in range(low, high+1)]
    rng.shuffle(columns)
    bands = []
    for x in columns:
        if len(bands) >= rng.choice((2, 2, 3, 3, 4)) or len(bands) >= len(columns):
            break
        charge = (x, y, z+1)
        if frame.blocks.get(charge, {}).get('kind') not in MATERIALS:
            continue
        styles = []
        if (x, y) not in pushed:
            styles.append('behind')
        styles.append('side')
        for style in styles:
            if style == 'behind':
                entry_cell = (x, y, z)
                if not frame.free(entry_cell) and frame.blocks.get(entry_cell, {}).get('kind') not in MATERIALS:
                    continue
                frame.blocks.pop(entry_cell, None)
                if not frame.put(entry_cell, 'observer', 'positive_z'):
                    continue
                hub = frame.add_hub(charge, entry_cell, 'behind')
            else:
                sides = [c for c in _free_lateral(frame, charge) if c[2] == z+1]
                if not sides:
                    continue
                rng.shuffle(sides)
                observer = sides[0]
                facing = SIDE_FACING[(charge[0]-observer[0], charge[1]-observer[1])]
                if not frame.put(observer, 'observer', facing):
                    continue
                hub = frame.add_hub(charge, observer, 'side')
            if hub is None:
                continue
            slots = [c for c in _free_lateral(frame, charge)
                     if c[2] == z+1 or c == (charge[0], charge[1], charge[2]+1)]
            rng.shuffle(slots)
            count = rng.randint(1, max(1, min(max_pistons, len(slots))))
            for slot in slots[:count]:
                if frame.piston(slot):
                    hub['pistons'].append(slot)
            if hub['pistons']:
                stage['hubs'].append(hub)
                stage['pistons'].extend(hub['pistons'])
                bands.append(hub)
                break
    if not stage['hubs']:
        return None
    frame.stages.append(stage)
    return stage


def hook_unit(rng, frame, charge, max_pistons=3, avoid=()):
    """已验证的拉驱接力单元：粘性活塞朝后，后方整组被拉前一格。

    粘性活塞挂在强充能块侧边（因此与推驱同刻被激活），它后方一格就是被拉
    推驱中心的强充能块；活塞回缩时把该中心整组拉前一格，随后该中心组脉冲
    并同时推出自己的目标。
    """
    slots = _free_lateral(frame, charge)
    rng.shuffle(slots)
    for slot in slots:
        cell = (slot[0], slot[1], slot[2]-1)
        if not frame.free(cell):
            continue
        if not frame.put(slot, 'sticky_piston', 'negative_z'):
            continue
        entry = compact_hub(rng, frame, cell, max_pistons, 0, avoid)
        if entry is None or not entry['pistons']:
            continue
        frame.sticky.append(slot)
        return entry
    return None


def add_pull_element(rng, frame, charge, columns):
    """给推驱中心补一个真实拉驱：粘性活塞前方带一个随组前进的方块。

    该方块随本组平移被活塞顶出一格，活塞通电多推一格、断电回缩再把它拉回，
    净位移仍为一格，同时产生引擎承认的真实回拉。位置必须避开负载列。
    """
    candidates = _free_lateral(frame, charge)
    front = (charge[0], charge[1], charge[2]+1)
    if frame.free(front):
        candidates.append(front)
    rng.shuffle(candidates)
    for slot in candidates:
        filler = (slot[0], slot[1], slot[2]+1)
        if not frame.free(filler):
            continue
        if not frame.put(slot, 'sticky_piston', 'positive_z'):
            continue
        # 填充块用玻璃：不参与黏附，不会把负载列拖走，但可被粘性活塞拉回。
        if not frame.put(filler, 'glass'):
            continue
        frame.sticky.append(slot)
        return filler
    return None


def _shuffled(rng, values):
    values = list(values)
    rng.shuffle(values)
    return values


def _fanout(rng, frame, relays, per_hub):
    """两层扇出：离合层活塞推动下一层推驱中心组，中心组再同时推目标。"""
    stage = relay_stage(rng, frame, relays, 1, True, per_hub)
    return stage


def _charges(frame):
    return [hub['charge'] for stage in frame.stages for hub in stage['hubs']]


def _root(rng, frame, hubs, spacing, max_pistons, reserve=0):
    """离合层规模受单活塞搬运上限约束，因此始终保持在十二块以内。"""
    root = root_stage(rng, frame, hubs, spacing, max_pistons, reserve)
    if not root:
        return None
    stage, push = root
    size = len({cell for hub in stage['hubs'] for cell in (hub['charge'], hub['observer'])}) \
        + len(stage['pistons'])
    size += sum(1 for cell in frame.blocks if cell[2] == 0 and cell not in
                {hub['charge'] for hub in stage['hubs']} | {hub['observer'] for hub in stage['hubs']}
                and cell not in set(stage['pistons']))
    if size > 11:
        return None
    return stage, push


def build(rng, category, band='中', attempts=8):
    if category == '推驱加拉驱':
        for _ in range(max(1, attempts)):
            out = pull_structure(rng)
            if out is not None:
                return out
        return None
    for _ in range(max(1, attempts)):
        out = _build_once(rng, category, band)
        if out is not None:
            return out
    return None

LAST_FAIL = []


def pull_group(rng, frame, charge, level, max_pistons=3):
    """在强充能块侧边挂朝后的粘性活塞，并在它后方搭一组被拉的推驱中心。

    被拉组用侧贴观察者（同层），整组被拉前一格后观察者脉冲、活塞同刻推目标。
    返回被拉组的 stage；找不到位置时返回 None。
    """
    slots = [c for c in _free_lateral(frame, charge) if c not in frame.blocks]
    rng.shuffle(slots)
    for slot in slots:
        cell = (slot[0], slot[1], slot[2]-1)
        if not frame.free(cell):
            continue
        if not frame.put(slot, 'sticky_piston', 'negative_z'):
            continue
        hub = compact_hub(rng, frame, cell, max_pistons)
        if hub is None or not hub['pistons']:
            continue
        frame.sticky.append(slot)
        stage = dict(level=level, hubs=[hub], pistons=list(hub['pistons']))
        frame.stages.append(stage)
        return stage
    return None


def pull_structure(rng):
    """四格厚拉驱结构：离合层 + 被拉的“输入带＋强充能带”。

    离合层：强充能块 + 侧贴观察者 + 推动块；一侧挂朝后的粘性活塞。
    被拉组是一条相连的带：输入带（z=-1）和强充能带（z=-2），带内若干块各自
    配一个观察者（同层侧贴或更后一层正对）。活塞回缩把整条带拉前一格，带内
    观察者到位后脉冲，强充能带上的活塞同刻推出全部目标，共跨四层。
    """
    frame = Frame(rng.choice(MATERIALS))
    material = frame.material
    side = rng.choice((1, -1))
    def at(x, y, z):
        return (side*x, y, z)
    clutch_charge = at(0, 0, 0)
    frame.put(clutch_charge, material)
    frame.put(at(0, -1, 0), 'observer', 'positive_y' if side > 0 else 'positive_y')
    frame.put(at(0, 1, 0), material)
    push = at(0, 1, 0)
    hook = at(1, 0, 0)
    frame.put(hook, 'sticky_piston', 'negative_z')
    frame.stages.append(dict(level=0, hubs=[dict(charge=clutch_charge, observer=at(0, -1, 0),
                                                 style='compact', pistons=[])], pistons=[]))
    columns = [1, 2]
    span = [at(x, 0, -1) for x in columns]
    band = [at(x, 0, -2) for x in columns]
    for cell in span + band:
        if not frame.free(cell):
            return None
    for cell in span:
        frame.put(cell, material)
    clutch_columns = {(x, y) for (x, y, z) in frame.blocks if z == 0}
    forbidden = {(x, y, z) for z in range(-8, 0) for (x, y) in clutch_columns}
    stage = dict(level=1, hubs=[], pistons=[])
    for cell in band:
        if not frame.free(cell):
            return None
        frame.put(cell, material)
        sides = [c for c in _free_lateral(frame, cell)
                 if c[2] == cell[2] and c not in forbidden]
        if not sides:
            return None
        if rng.random() < .5:
            # 侧贴：观察者与强充能块同层，输出端正对这块
            candidate = [c for c in sides]
            rng.shuffle(candidate)
            observer = candidate[0]
            facing = SIDE_FACING[(cell[0]-observer[0], cell[1]-observer[1])]
        elif frame.free((cell[0], cell[1], cell[2]-1)):
            # 正后方：观察者在前一层，朝前对这块
            observer, facing = (cell[0], cell[1], cell[2]-1), 'positive_z'
        else:
            continue
        if not frame.put(observer, 'observer', facing):
            continue
        hub = frame.add_hub(cell, observer, 'side' if facing != 'positive_z' else 'behind')
        slots = [c for c in _free_lateral(frame, cell)
                 if c[2] == cell[2] and c not in forbidden]
        rng.shuffle(slots)
        count = rng.randint(1, max(1, min(3, len(slots))))
        for slot in slots[:count]:
            if frame.piston(slot):
                hub['pistons'].append(slot)
        if hub['pistons']:
            stage['hubs'].append(hub)
            stage['pistons'].extend(hub['pistons'])
    if len(stage['pistons']) < 3:
        return None
    frame.stages.append(stage)
    if add_loads(frame, stage, len(stage['pistons'])) < 3:
        return None
    return frame, push, dict(category='推驱加拉驱', stages=2, hooks=1)


def _build_once(rng, category, band='中'):
    """单次尝试；成功返回 (frame, push, meta)，否则 None。

    * 同时推驱：离合层活塞各推一个彼此独立、侧贴观察者的推驱中心，全部目标同刻。
      目标多时才再加一级（多一层换更多驱动位），不为了厚度去垫层。
    * 多时序推驱：一部分活塞直接推目标（时序 1），一部分推下一级中心（时序 2），
      再用朝后的粘性活塞把后面一组拉进来（时序 3）——推驱与拉驱真正结合。
    """
    frame = Frame(rng.choice(MATERIALS))
    plan = PLAN[band]
    root = _root(rng, frame, rng.choice(plan['hubs']), rng.choice(plan['spacing']),
                 rng.choice(plan['pistons']))
    if not root:
        return None
    stage0, push = root
    pistons = _shuffled(rng, stage0['pistons'])
    if category == '同时推驱':
        direct = 0
        if band != '高':
            direct = _add_some(frame, stage0, rng.randint(0, max(0, len(pistons)-1)))
        used = {(t['x'], t['y']) for t in frame.targets}
        relays = [p for p in pistons if (p[0], p[1]) not in used]
        relays = relays[:min(len(relays), rng.randint(*plan['relays']))]
        if not relays:
            return None
        stage = relay_stage(rng, frame, relays, 1, 0.0, rng.choice(plan['per_hub']))
        if stage is None:
            return None
        if band == '高' and rng.random() < .8:
            second = relay_stage(rng, frame, _shuffled(rng, stage['pistons'])[:rng.randint(2, 3)],
                                 2, 0.0, rng.choice(plan['per_hub']))
            if second is not None:
                stage = second
        if add_loads(frame, stage, len(stage['pistons'])) < 3:
            return None
        return frame, push, dict(category=category, stages=len(frame.stages), hooks=0)
    if category == '推驱加拉驱':
        return None  # 由 pull_structure 负责
    # 多时序推驱：推驱 + 拉驱结合
    direct = _add_some(frame, stage0, max(1, len(pistons)//3))
    used = {(t['x'], t['y']) for t in frame.targets}
    relays = [p for p in pistons if (p[0], p[1]) not in used]
    relays = relays[:min(len(relays), rng.randint(1, 2))]
    stage = None
    if relays:
        stage = relay_stage(rng, frame, relays, 1, 0.0, rng.choice(plan['per_hub']))
    pulled = None
    for charge in _shuffled(rng, _charges(frame)):
        pulled = pull_group(rng, frame, charge, 2, rng.choice((2, 3)))
        if pulled is not None:
            break
    if pulled is None and stage is None:
        return None
    for layer in (stage, pulled):
        if layer is not None:
            add_loads(frame, layer, len(layer['pistons']))
    groups = len({t['order'] for t in frame.targets})
    if len(frame.targets) < 4 or groups < 2:
        return None
    return frame, push, dict(category=category, stages=len(frame.stages), hooks=1 if pulled else 0)


def pull_structure(rng):
    """四格厚拉驱结构：离合层 + 被拉的“输入带＋强充能带”。

    离合层：强充能块 + 侧贴观察者 + 推动块；一侧挂朝后的粘性活塞。
    被拉组是一条相连的带：输入带（z=-1）和强充能带（z=-2），带内若干块各自
    配一个观察者（同层侧贴或更后一层正对）。活塞回缩把整条带拉前一格，带内
    观察者到位后脉冲，强充能带上的活塞同刻推出全部目标，共跨四层。
    """
    frame = Frame(rng.choice(MATERIALS))
    material = frame.material
    side = rng.choice((1, -1))
    def at(x, y, z):
        return (side*x, y, z)
    clutch_charge = at(0, 0, 0)
    frame.put(clutch_charge, material)
    frame.put(at(0, -1, 0), 'observer', 'positive_y' if side > 0 else 'positive_y')
    frame.put(at(0, 1, 0), material)
    push = at(0, 1, 0)
    hook = at(1, 0, 0)
    frame.put(hook, 'sticky_piston', 'negative_z')
    frame.stages.append(dict(level=0, hubs=[dict(charge=clutch_charge, observer=at(0, -1, 0),
                                                 style='compact', pistons=[])], pistons=[]))
    columns = [1, 2]
    span = [at(x, 0, -1) for x in columns]
    band = [at(x, 0, -2) for x in columns]
    for cell in span + band:
        if not frame.free(cell):
            return None
    for cell in span:
        frame.put(cell, material)
    clutch_columns = {(x, y) for (x, y, z) in frame.blocks if z == 0}
    forbidden = {(x, y, z) for z in range(-8, 0) for (x, y) in clutch_columns}
    stage = dict(level=1, hubs=[], pistons=[])
    for cell in band:
        if not frame.free(cell):
            return None
        frame.put(cell, material)
        sides = [c for c in _free_lateral(frame, cell)
                 if c[2] == cell[2] and c not in forbidden]
        if not sides:
            return None
        if rng.random() < .5:
            # 侧贴：观察者与强充能块同层，输出端正对这块
            candidate = [c for c in sides]
            rng.shuffle(candidate)
            observer = candidate[0]
            facing = SIDE_FACING[(cell[0]-observer[0], cell[1]-observer[1])]
        elif frame.free((cell[0], cell[1], cell[2]-1)):
            # 正后方：观察者在前一层，朝前对这块
            observer, facing = (cell[0], cell[1], cell[2]-1), 'positive_z'
        else:
            continue
        if not frame.put(observer, 'observer', facing):
            continue
        hub = frame.add_hub(cell, observer, 'side' if facing != 'positive_z' else 'behind')
        slots = [c for c in _free_lateral(frame, cell)
                 if c[2] == cell[2] and c not in forbidden]
        rng.shuffle(slots)
        count = rng.randint(1, max(1, min(3, len(slots))))
        for slot in slots[:count]:
            if frame.piston(slot):
                hub['pistons'].append(slot)
        if hub['pistons']:
            stage['hubs'].append(hub)
            stage['pistons'].extend(hub['pistons'])
    if len(stage['pistons']) < 3:
        return None
    frame.stages.append(stage)
    if add_loads(frame, stage, len(stage['pistons'])) < 3:
        return None
    return frame, push, dict(category='推驱加拉驱', stages=2, hooks=1)


def _build_once(rng, category, band='中'):
    """单次尝试；成功返回 (frame, push, meta)，否则 None。"""
    frame = Frame(rng.choice(MATERIALS))
    plan = dict(低=dict(hubs=(1,), spacing=(2, 3), pistons=(3, 4), relays=(1, 2), per_hub=(2, 3)),
                中=dict(hubs=(1, 2), spacing=(2, 3), pistons=(2, 3), relays=(2, 3), per_hub=(3, 4)),
                高=dict(hubs=(2,), spacing=(3, 3), pistons=(3, 3), relays=(4, 4), per_hub=(4, 5)))[band]
    hubs = rng.choice(plan['hubs'])
    reserve = 1 if category == '推驱加拉驱' else 0
    root = _root(rng, frame, hubs, rng.choice(plan['spacing']), rng.choice(plan['pistons']), reserve)
    if not root:
        return None
    stage0, push = root
    pistons = _shuffled(rng, stage0['pistons'])
    if category == '推驱加拉驱':
        # 拉驱课程：离合层只负责供能和挂钩，输出目标全部由被拉的推驱中心组
        # 在回拉到位后同刻推出，因此目标仍然同刻。
        pulled = []
        behind_push = {(push[0], push[1], z) for z in range(push[2]-12, push[2])}
        for charge in _shuffled(rng, _charges(frame)):
            entry = hook_unit(rng, frame, charge, rng.choice((2, 3, 3)), behind_push)
            if entry is not None:
                pulled.append(entry)
            if len(pulled) >= rng.choice((1, 1, 2)):
                break
        if not pulled:
            return None
        stage = dict(level=1, hubs=pulled,
                     pistons=[p for entry in pulled for p in entry['pistons']])
        frame.stages.append(stage)
        if add_loads(frame, stage, len(stage['pistons'])) < 3:
            return None
        return frame, push, dict(category=category, stages=2, hooks=len(pulled))
    if category == '多时序推驱' and len(pistons) >= 2:
        _add_some(frame, stage0, 1)
    used = {(t['x'], t['y']) for t in frame.targets}
    relays = [p for p in pistons if (p[0], p[1]) not in used]
    relays = relays[:min(len(relays), rng.randint(*plan['relays']))]
    if not relays:
        return None
    stage = band_stage(rng, frame, relays, 1, rng.choice(plan['per_hub']))
    if stage is None:
        return None
    if add_loads(frame, stage, len(stage['pistons'])) < 3:
        return None
    hooks = 0
    groups = len({t['order'] for t in frame.targets})
    if category == '多时序推驱' and groups < 2:
        return None
    return frame, push, dict(category=category, stages=2, hooks=hooks)
