"""按输入与推拉接口组合运行单元，分支数、方向、输出和材料均可变化。"""

from copy import deepcopy
import random

from ..domain_rules import proposal_issues
from ..serialization import digest
from .modules import AXES, instantiate, orient, xyz
from .transport import transport_valid
from .config import COMPOSITION_LIMITS


def normalize(blocks, targets, push, limits=None, diagnostics=None):
    limits = COMPOSITION_LIMITS if limits is None else limits
    points = [b['position'] for b in blocks]+targets
    ox = min(p['x'] for p in points); oy = min(p['y'] for p in points)
    oz = max(b['position']['z'] for b in blocks)+2
    for p in [*points, push]:
        p['x'] -= ox; p['y'] -= oy; p['z'] -= oz
    width = max(p['x'] for p in points)+1; height = max(p['y'] for p in points)+1
    depth = -min(b['position']['z'] for b in blocks)-1
    if any(value > limits[key] for key, value in
           [('width', width), ('height', height), ('depth', depth), ('volume', width*height*depth)]):
        if diagnostics is not None:
            diagnostics.update(reason='达到空间资源上限', width=width, height=height, depth=depth)
        return None
    if len({(t['x'], t['y']) for t in targets}) != len(targets):
        if diagnostics is not None:
            diagnostics['reason'] = '输出负载列重叠'
        return None
    task = dict(width=width, height=height, depth=depth, targets=sorted(targets,key=lambda t:(t['x'],t['y'])),
                max_ticks=64, rounds=3, load_blocks=10)
    return dict(task=task, proposal=dict(blocks=blocks, push=push))


def compose(library, rng, max_nodes=5, min_nodes=1, limits=None, stop_probability=None, diagnostics=None):
    limits = COMPOSITION_LIMITS if limits is None else limits
    occupied, targets, topology, nodes = {}, [], [], []
    frontier = [(dict(x=0, y=0, z=0), None, 0, (0,0,-1))]
    modules = library['modules']
    while frontier:
        anchor, parent, tick, driver = frontier.pop(0)
        remaining = max_nodes-len(topology)-len(frontier)
        pool = [m for m in modules if len(m['ports']) < remaining
                and (frontier or len(topology)+1 >= min_nodes or m['ports'])]
        # 专家中的反向观察者、分叉和混材单元保持足够占比，避免程序化直链淹没它们。
        prefer_expert = rng.random() < .7
        preferred = [m for m in pool if bool(m.get('procedural')) != prefer_expert]
        if not topology and remaining >= 4 and rng.random() < .25:
            branched = [m for m in preferred if len(m['ports']) >= 2]
            preferred = branched or preferred
        if preferred:
            pool = preferred
        if stop_probability is not None:
            terminal = rng.random() < stop_probability
            preferred = [m for m in pool if (not m['ports']) == terminal]
            pool = preferred or pool
        rng.shuffle(pool)
        placed = False
        for original in pool[:32]:
            m = orient(original, rng.choice((False,True)), rng.choice((-1,1)), rng.choice((-1,1)), rng.choice((False,True)))
            capacity = 12-len(m['core'])
            options = m.get('slots', m['outputs'])
            chosen = rng.sample(options, rng.randint(0, min(capacity, len(options))))
            if not chosen and not m['ports']:
                continue
            blocks, out, ports = instantiate(m,anchor,chosen)
            for t in out:
                t['order']=tick+6
            if len(blocks)>12 or any(xyz(b['position']) in occupied for b in blocks):
                continue
            if any((t['x'],t['y']) in {(v['x'],v['y']) for v in targets} for t in out):
                continue
            trial = dict(blocks=[*occupied.values(),*blocks],push=dict(x=0,y=0,z=0))
            if proposal_issues(trial):
                continue
            moving=dict(blocks=blocks,anchor=anchor,parent=parent,tick=tick,driver=driver)
            if not transport_valid([*nodes,moving]):
                continue
            nodes.append(moving)
            occupied.update({xyz(b['position']):b for b in blocks});targets.extend(out)
            index=len(topology)
            topology.append(dict(module=original['id'],parent=parent,anchor=anchor,
                                 variant=digest(m)[:16],outputs=len(out),branches=len(ports)))
            for port in ports:
                p=port['position']
                frontier.append(({**p,'z':p['z']+(-1 if port['kind']=='pull' else 2)},index,
                                 tick+(8 if port['kind']=='pull' else 4),xyz(p)))
            placed=True
            break
        if not placed:
            if diagnostics is not None:
                diagnostics.update(reason='当前随机装配分支无法接续', partial_nodes=len(topology))
            return None
    if diagnostics is not None:
        diagnostics.update(assembled_nodes=len(topology), outputs=len(targets))
    if not targets or len(targets)>limits['targets']:
        if diagnostics is not None:
            diagnostics['reason'] = '达到目标数量资源上限' if targets else '未产生输出'
        return None
    order={t:i+1 for i,t in enumerate(sorted({t['order'] for t in targets}))}
    for t in targets:
        t['order']=order[t['order']]
    row=normalize(list(occupied.values()),targets,dict(x=0,y=0,z=0),limits,diagnostics)
    if row is None or proposal_issues(row['proposal']):
        if row is not None and diagnostics is not None:
            diagnostics['reason'] = '完整结构违反领域约束'
        return None
    # 同一单元树的输出选择与相对摆放后代保持同组，避免训练和保留集共享骨架。
    groups = {m['id']: m.get('canonical',m['id']) for m in modules}
    def tree(index):
        return [groups[topology[index]['module']], sorted(
            [tree(i) for i,n in enumerate(topology) if n['parent']==index], key=str)]
    row.update(source='motion_module_assembly_v1',family='expert_composition',topology=topology,
               group=digest(tree(0)),id=digest([row['task'],row['proposal']])[:24])
    return row
