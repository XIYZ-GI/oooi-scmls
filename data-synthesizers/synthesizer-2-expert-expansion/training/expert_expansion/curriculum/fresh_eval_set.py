"""从课程新增记录里冻结模型未见过的评估题，只导出需求。"""

import argparse
import collections
import hashlib
import json
import random
import sqlite3
from pathlib import Path

from ...reinforcement.demands import geometry
from ...serialization import write_json


def positions_geometry(task):
    return geometry({**task, 'targets': [{**t, 'order': 1} for t in task['targets']]})


def training_keys(path):
    """训练文件的记录 id 与两类目标几何。"""
    ids, ordered, positions = set(), set(), set()
    with Path(path).open() as handle:
        for line in handle:
            row = json.loads(line)
            ids.add(row['id'])
            ordered.add(geometry(row['task']))
            positions.add(positions_geometry(row['task']))
    return ids, ordered, positions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--training', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--count', type=int, default=200)
    parser.add_argument('--seed', type=int, default=20260922)
    args = parser.parse_args()
    ids, ordered, positions = training_keys(args.training)
    uri = 'file:%s?mode=ro' % Path(args.database).resolve()
    db = sqlite3.connect(uri, uri=True)
    rows = [json.loads(body) for (body,) in db.execute('SELECT body FROM records ORDER BY id')]
    db.close()
    fresh, duplicated, seen_geometry = [], 0, 0
    for row in rows:
        if row['id'] in ids:
            duplicated += 1
            continue
        if geometry(row['task']) in ordered or positions_geometry(row['task']) in positions:
            seen_geometry += 1
            continue
        fresh.append(row)
    if not fresh:
        parser.error('没有找到与训练集不重叠的新记录')
    rng = random.Random(args.seed)
    rng.shuffle(fresh)
    selected = fresh[:args.count]
    cases = [dict(id=row['id'], cohort=row['split'], task=row['task'], coverage=row['coverage'],
                  actual_depth=row['actual_depth'], reference_blocks=len(row['proposal']['blocks']),
                  reference_nodes=len(row['topology'])) for row in selected]
    args.output.mkdir(parents=True, exist_ok=True)
    write_json(args.output/'eval-tasks.json', dict(
        source=str(args.database), training=str(args.training), protocol='curriculum_fresh_requirement_only_v1',
        cases=cases, case_count=len(cases), cohorts=dict(collections.Counter(c['cohort'] for c in cases)),
        candidates=len(fresh), skipped_training_ids=duplicated, skipped_seen_geometry=seen_geometry,
        note='只取训练集完全未出现的记录，仅提供目标点、时序与允许厚度；参考结构不参与生成。'))
    print(json.dumps(dict(selected=len(cases), candidates=len(fresh), skipped_ids=duplicated,
                          skipped_geometry=seen_geometry,
                          cohorts=dict(collections.Counter(c['cohort'] for c in cases))), ensure_ascii=False))


if __name__ == '__main__':
    main()
