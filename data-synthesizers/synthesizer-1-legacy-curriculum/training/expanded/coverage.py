"""统计实际训练课程覆盖，不把允许厚度或对称变体当作新构造。"""

import argparse
from collections import Counter, defaultdict
import hashlib
from pathlib import Path

from ..data import read_examples
from ..serialization import write_json


def summarize(records):
    families = defaultdict(list)
    for row in records:
        if row['usage'] == 'fit':
            families[row['family']].append(row)
    result = {}
    for family, rows in families.items():
        dimensions, depths, targets, orders, allowed, ticks = (Counter() for _ in range(6))
        for row in rows:
            task = row['task']
            zs = [b['position']['z'] for b in row['proposal']['blocks']]
            dimensions[f"{task['width']}×{task['height']}"] += 1
            depths[max(zs)-min(zs)+1] += 1
            allowed[task['depth']] += 1
            targets[len(task['targets'])] += 1
            orders[len({t['order'] for t in task['targets']})] += 1
            rounds = row.get('evaluation', {}).get('rounds', [])
            if rounds:
                ticks[','.join(map(str, sorted(set(rounds[0]['ticks']))))] += 1
        result[family] = {
            'records': len(rows), 'source_groups': len({r['group'] for r in rows}),
            'dimensions': dict(dimensions), 'actual_depth': dict(sorted(depths.items())),
            'allowed_depth': dict(sorted(allowed.items())),
            'target_counts': dict(sorted(targets.items())),
            'timing_group_counts': dict(sorted(orders.items())),
            'reference_first_round_ticks': dict(ticks),
        }
    return result


def main():
    parser = argparse.ArgumentParser(description='保存训练课程的尺寸、目标、时序与实际厚度分布')
    parser.add_argument('--data', required=True)
    args = parser.parse_args()
    root = Path(args.data)
    source = root/'examples.jsonl'
    write_json(root/'coverage.json', {
        'examples_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'families': summarize(read_examples(source)),
        'scope': '记录数包含对称变换与目标子集；来源组数不等同独立机械原理数量。',
        'timing': '训练条件为同刻分组与先后顺序，不是指定绝对游戏刻或任意间隔。',
        'sampling': '课程按机械规则构造并模拟确认，不是任意尺寸、目标位置和时序的均匀随机采样。',
        'slack': '扩大允许厚度而保留原结构；这类记录不代表学到更厚的新构造。',
    })


if __name__ == '__main__':
    main()
