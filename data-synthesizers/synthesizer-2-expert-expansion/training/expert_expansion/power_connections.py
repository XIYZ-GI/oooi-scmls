"""单次搬运课程保守排除后继分支向上游活塞回授供电的连接。"""

from .modules import xyz

CONDUCTORS = {'slime_block', 'honey_block', 'iron_block', 'light_blue_glazed_terracotta'}


def facing_vector(spec):
    sign, axis = spec['facing'].split('_')
    return tuple((1 if sign == 'positive' else -1) if a == axis else 0 for a in ('x', 'y', 'z'))


def supplies_upstream(source, upstream):
    world = {xyz(b['position']): b['block'] for n in (source, upstream) for b in n['blocks']}
    outputs = []
    for b in source['blocks']:
        if b['block']['kind'] == 'observer':
            p = xyz(b['position'])
            q = tuple(a+d for a,d in zip(p, facing_vector(b['block'])))
            outputs.append((p, q))
    for b in upstream['blocks']:
        if b['block']['kind'] not in ('piston', 'sticky_piston'):
            continue
        p = xyz(b['position'])
        if p not in {xyz(c['driver']) for c in upstream.get('children', [])}:
            continue
        front = tuple(a+d for a,d in zip(p, facing_vector(b['block'])))
        for origin, output in outputs:
            if output == p and origin != front:
                return True
            if (world.get(output, {}).get('kind') in CONDUCTORS and output != front
                    and sum(abs(a-b) for a,b in zip(p, output)) == 1):
                return True
    return False
