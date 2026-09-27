"""对称去重与需求几何隔离；推动点参与完整结构身份。"""

from itertools import product

from ..serialization import digest
from ..structure_generator.geometry import canonical


def identities(row):
    targets = row['task']['targets']
    variants = []
    for swap, sx, sy in product((False, True), (-1, 1), (-1, 1)):
        points = [(sx*t['y' if swap else 'x'], sy*t['x' if swap else 'y'], t['order']) for t in targets]
        ox, oy = min(p[0] for p in points), min(p[1] for p in points)
        variants.append(digest(sorted((x-ox, y-oy, order) for x, y, order in points)))
    geometry = min(variants)
    proposal = row['proposal']
    key = canonical(proposal['blocks'], [*targets, {**proposal['push'], 'order': 0}])
    outputs = {(t['x'], t['y'], t['z']-2) for t in targets}
    skeleton = canonical([b for b in proposal['blocks']
                          if tuple(b['position'][a] for a in ('x', 'y', 'z')) not in outputs])
    bucket = int(geometry[:8], 16) % 10
    return dict(id=digest([row['task'], proposal])[:24], canonical=key, skeleton=skeleton,
                geometry=geometry, split='heldout' if bucket == 0 else 'development' if bucket == 1 else 'train')
