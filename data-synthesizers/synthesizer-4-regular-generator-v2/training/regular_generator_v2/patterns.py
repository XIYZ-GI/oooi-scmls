"""分别描述时序条带、重复图案与实体方块截面的重复，不用密度替代规律。"""

from collections import Counter


def sequence_pattern(sequence):
    runs = []
    for value in sequence:
        if runs and runs[-1]['value'] == value:
            runs[-1]['length'] += 1
        else:
            runs.append(dict(value=value, length=1))
    period = next((p for p in range(1, len(sequence)//3+1)
                   if len(sequence) % p == 0 and all(v == sequence[i % p]
                                                    for i, v in enumerate(sequence))), None)
    return dict(runs=runs, period=period, repeats=len(sequence)//period if period else 0)


def timing_pattern(rectangle, orders):
    x0, y0, width, height = (rectangle[k] for k in ('x', 'y', 'width', 'height'))
    rows = [[orders[x, y] for x in range(x0, x0+width)] for y in range(y0, y0+height)]
    columns = [list(c) for c in zip(*rows)]
    bands = []
    for axis, values in (('x', columns), ('y', rows)):
        if all(len(set(v)) == 1 for v in values):
            sequence = [v[0] for v in values]
            pattern = sequence_pattern(sequence)
            distinct = sorted(set(sequence))
            monotone = sequence == sorted(sequence) or sequence == sorted(sequence, reverse=True)
            bands.append(dict(axis=axis, groups=distinct, ordered=monotone,
                              equal_width=len({r['length'] for r in pattern['runs']}) == 1,
                              **pattern))
    return dict(groups=sorted({v for row in rows for v in row}), bands=bands,
                repeated_rows=sequence_pattern(rows), repeated_columns=sequence_pattern(columns))


def structure_pattern(blocks):
    """整列纵深归一后的方块签名重复；只作诊断，不以此代替完整物理验收。"""
    result = {}
    for axis, other in (('x', 'y'), ('y', 'x')):
        columns = {}
        for b in blocks:
            p, spec = b['position'], b['block']
            columns.setdefault(p[axis], []).append((p[other], p['z'], spec['kind'], spec['facing']))
        signatures = []
        for _, column in sorted(columns.items()):
            low = min(v[1] for v in column)
            signatures.append(tuple(sorted((a, z-low, k, f) for a, z, k, f in column)))
        counts = Counter(signatures)
        result[axis] = dict(columns=len(signatures), distinct=len(counts),
                            repeated_columns=sum(n for n in counts.values() if n >= 2),
                            most_common=max(counts.values(), default=0))
    return result
