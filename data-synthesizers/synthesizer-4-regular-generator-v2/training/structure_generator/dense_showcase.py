"""优先展示密集目标、入口延伸和实际大截面的不同骨架。"""

import math

from .reduction import reduce
from .verification import verify_pulls


def select(rows, count, extension_share=.7):
    chosen, seen, rejected = [],set(),set()
    extension_target = math.ceil(count*extension_share)
    def score(row):
        c,m = row['coverage'],row['mechanisms']
        return (c['density'],c['targets'],m['extended_input_pulls'],
                c['groups'],m['secondary_useful_lateral_observers'])
    def pick(predicate):
        for row in sorted((r for r in rows if predicate(r)),key=score,reverse=True):
            if row['skeleton'] in seen or row['id'] in rejected:
                continue
            selected,reason = reduce(row)
            if reason or selected['skeleton'] in seen or not predicate(selected):
                rejected.add(row['id'])
                continue
            checks,reason = verify_pulls(selected)
            if reason:
                rejected.add(row['id'])
                continue
            selected['pull_ablation'] = checks
            chosen.append(selected)
            seen.update((row['skeleton'],selected['skeleton']))
            return True
        return False
    extended = lambda r:r['mechanisms']['extended_input_pulls']>0
    dense = lambda r:r['coverage']['density']>=.4 and r['coverage']['targets']>=13
    # 大尺寸也必须有真实目标与功能，单独保留代表例，避免只选最小包围框。
    if count:
        pick(lambda r:extended(r) and min(r['coverage']['width'],r['coverage']['height'])>=6
             and max(r['coverage']['width'],r['coverage']['height'])>=10
             and r['coverage']['targets']>=20)
    while sum(extended(r) for r in chosen)<extension_target and len(chosen)<count:
        if not pick(lambda r:extended(r) and dense(r)):
            break
    if len(chosen)<count:
        pick(lambda r:r['family']=='推拉结合同推' and r['coverage']['targets']>=10)
    if len(chosen)<count:
        pick(lambda r:r['family']=='多目标同推' and dense(r))
    while len(chosen)<count:
        if not pick(dense):
            break
    return chosen
