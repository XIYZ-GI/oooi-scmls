"""将真实搬运组分解为至多十二块的输入单元、输出槽和后继接口。"""

from collections import defaultdict
from copy import deepcopy
import json

from ..serialization import digest, write_json
from .config import ROOT

AXES = ('x', 'y', 'z')


def xyz(p):
    return tuple(p[a] for a in AXES)


def relative(p, anchor):
    return {a: p[a]-anchor[a] for a in AXES}


def compile_library():
    reports = json.loads((ROOT/'expert-audit.json').read_text())
    modules, recipes = {}, []
    for expert in reports:
        if (len(expert['evaluation']['rounds']) != 3
                or not expert['evaluation']['foundation']['translation']):
            raise ValueError('专家轨迹未完成，不能提取运行单元：'+expert['name'])
        inactive = {xyz(p['initial']) for c in expert['evaluation']['foundation']['cycles']
                    for p in c['inactive_pistons']}
        owner, nodes = {}, []
        for index, op in enumerate(expert['operations']):
            for b in op['blocks']:
                pos = xyz(b['position'])
                if pos in owner:
                    raise ValueError('当前分解只支持每轮净搬运一次的单元')
                owner[pos] = index
        if len(owner) != len(expert['proposal']['blocks']):
            raise ValueError('运行单元没有覆盖整个本体')
        for index, op in enumerate(expert['operations']):
            piston = op['piston'].get('position')
            anchor = expert['proposal']['push'] if piston is None else {
                **piston, 'z': piston['z']+(-1 if op['kind'] == 'pull' else 2)}
            if xyz(anchor) not in {xyz(b['position']) for b in op['blocks']}:
                raise ValueError('单元输入不在真实搬运组内')
            ports = []
            children = []
            for child, next_op in enumerate(expert['operations']):
                p = next_op['piston'].get('position')
                if p is not None and owner[xyz(p)] == index:
                    ports.append(dict(position=relative(p, anchor), kind=next_op['kind']))
                    children.append(child)
            outputs = []
            for t in expert['task']['targets']:
                p = {a: t[a] for a in AXES}; p['z'] -= 2
                if owner.get(xyz(p)) == index:
                    outputs.append(relative(p, anchor))
            output_positions = {xyz(p) for p in outputs}
            core = []
            for b in op['blocks']:
                p = relative(b['position'], anchor)
                if xyz(p) not in output_positions:
                    core.append(dict(position=p, block=b['block']))
            module = dict(core=sorted(core, key=lambda b: xyz(b['position'])),
                          outputs=sorted(outputs, key=xyz), ports=ports,
                          input_kind=next(b['block']['kind'] for b in op['blocks'] if b['position'] == anchor))
            key = digest(module)[:20]
            if key not in modules:
                modules[key] = dict(id=key, **module, sources=[])
            modules[key]['sources'].append(dict(expert=expert['name'], node=index))
            # 保留原样分解；另提供不导电的被搬运填充块，避免把无驱动用途的活塞带入课程。
            if any(xyz(b['position']) in inactive for b in op['blocks']):
                variant = deepcopy(module)
                for b in variant['core']:
                    absolute = tuple(b['position'][a]+anchor[a] for a in AXES)
                    if absolute in inactive:
                        b['block'] = dict(kind='glass', facing='positive_z')
                vkey = digest(variant)[:20]
                modules[vkey] = dict(id=vkey, **variant, sources=[dict(expert=expert['name'], node=index)],
                                     normalization='未激活的非供电填充活塞替换为玻璃，完整装配仍须三轮验收')
            nodes.append(dict(module=key, anchor=anchor, children=children))
        recipes.append(dict(name=expert['name'], id=expert['id'], nodes=nodes,
                            task=expert['task'], push=expert['proposal']['push']))
    value = dict(modules=list(modules.values()), recipes=recipes,
        note='单元来自真实搬运事件；保留供电、反粘、输出及后继接口。原样重装是分解正确性的核对，不是新设计数量。')
    write_json(ROOT/'module-library.json', value)
    return value


def orient(module, swap=False, sx=1, sy=1, materials=False):
    module = deepcopy(module)
    for p in [*[b['position'] for b in module['core']], *module['outputs'],
              *module.get('slots', []), *[p['position'] for p in module['ports']]]:
        x, y = p['x'], p['y']
        p.update(x=sx*(y if swap else x), y=sy*(x if swap else y))
    for b in module['core']:
        spec = b['block']; sign, axis = spec['facing'].split('_')
        if axis != 'z':
            if swap:
                axis = 'y' if axis == 'x' else 'x'
            direction = (1 if sign == 'positive' else -1)*(sx if axis == 'x' else sy)
            spec['facing'] = ('positive_' if direction > 0 else 'negative_')+axis
        if materials:
            spec['kind'] = {'slime_block': 'honey_block', 'honey_block': 'slime_block'}.get(spec['kind'], spec['kind'])
    return module


def instantiate(module, anchor, chosen=None):
    chosen = module['outputs'] if chosen is None else chosen
    blocks = deepcopy(module['core'])+[
        dict(position=dict(p), block=dict(kind='piston', facing='positive_z')) for p in chosen]
    for b in blocks:
        b['position'] = {a: b['position'][a]+anchor[a] for a in AXES}
    targets = [{**{a: p[a]+anchor[a] for a in AXES}, 'order': 1} for p in chosen]
    for t in targets:
        t['z'] += 2
    ports = [dict(position={a: p['position'][a]+anchor[a] for a in AXES}, kind=p['kind']) for p in module['ports']]
    return blocks, targets, ports


def reconstruct(recipe, library):
    modules = {r['id']: r for r in library['modules']}
    blocks = []
    for node in recipe['nodes']:
        b, _, _ = instantiate(modules[node['module']], node['anchor'])
        blocks.extend(b)
    return dict(task=deepcopy(recipe['task']), proposal=dict(blocks=blocks, push=recipe['push']),
                name=recipe['name'], source='expert_module_reconstruction')


if __name__ == '__main__':
    library = compile_library()
    print(json.dumps(dict(modules=len(library['modules']), recipes=len(library['recipes'])), ensure_ascii=False))
