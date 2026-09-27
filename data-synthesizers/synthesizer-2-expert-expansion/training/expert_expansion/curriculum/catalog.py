"""进程内缓存静态单元信息，直接抽取候选而不反复打乱整个库。"""

from ...serialization import digest


class Catalog:
    def __init__(self, modules):
        self.modules = modules
        self.canonical = {m['id']: m.get('canonical', m['id']) for m in modules}
        self.signatures = {id(m): digest(m)[:16] for m in modules}
        self.pools = {}

    def candidates(self, rng, remaining, need_child, terminal, count):
        key = remaining, need_child
        if key not in self.pools:
            eligible = [m for m in self.modules if len(m['ports']) < remaining
                        and (not need_child or m['ports'])]
            self.pools[key] = ([m for m in eligible if not m['ports']],
                               [m for m in eligible if m['ports']])
        leaves, branches = self.pools[key]
        first, second = (leaves, branches) if terminal else (branches, leaves)
        selected = rng.sample(first, min(count, len(first)))
        selected.extend(rng.sample(second, min(count-len(selected), len(second))))
        return selected


def instantiate(module, anchor, chosen):
    axes = ('x', 'y', 'z')
    blocks = [dict(position={a: b['position'][a]+anchor[a] for a in axes},
                   block=dict(b['block'])) for b in module['core']]
    blocks.extend(dict(position={a: p[a]+anchor[a] for a in axes},
                       block=dict(kind='piston', facing='positive_z')) for p in chosen)
    targets = [{**{a: p[a]+anchor[a] for a in axes}, 'order': 1} for p in chosen]
    for target in targets:
        target['z'] += 2
    ports = [dict(position={a: p['position'][a]+anchor[a] for a in axes}, kind=p['kind'])
             for p in module['ports']]
    return blocks, targets, ports
