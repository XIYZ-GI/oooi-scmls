"""从新课程数据集中冻结评估题：只保留需求，不给结构答案。"""

import argparse
import collections
import hashlib
import json
import sqlite3
from pathlib import Path

from ...reinforcement.demands import geometry
from ...serialization import write_json
from .config import OUTPUT
from .stage4_dataset import DEFAULT_EXPORT

EVAL_SPLITS = ('development', 'heldout')


def positions_geometry(task):
    """忽略时序的目标布局几何，用于隔离核对。"""
    return geometry({**task, 'targets': [{**t, 'order': 1} for t in task['targets']]})


def load_rows(database):
    uri = 'file:%s?mode=ro' % Path(database).resolve()
    db = sqlite3.connect(uri, uri=True)
    try:
        return [json.loads(body) for (body,) in db.execute('SELECT body FROM records ORDER BY id')]
    finally:
        db.close()


def requirement(row, cohort):
    """只导出模型需要的需求字段，参考结构不进入评估输入。"""
    task = row['task']
    return dict(id=row['id'], cohort=cohort, task=task,
                coverage=row['coverage'], actual_depth=row['actual_depth'],
                reference_blocks=len(row['proposal']['blocks']),
                reference_nodes=len(row['topology']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=OUTPUT / 'records.sqlite3')
    parser.add_argument('--output', type=Path, default=DEFAULT_EXPORT)
    parser.add_argument('--validation-size', type=int, default=256)
    parser.add_argument('--seed', type=int, default=20260922)
    args = parser.parse_args()
    rows = load_rows(args.database)
    grouped = collections.defaultdict(list)
    for row in rows:
        grouped[row['split']].append(row)
    train, evaluation = grouped['train'], [row for split in EVAL_SPLITS for row in grouped[split]]
    if not train or not evaluation:
        parser.error('训练集或评估集为空，不能冻结题目')
    train_order = {geometry(row['task']) for row in train}
    train_position = {positions_geometry(row['task']) for row in train}
    leaked = [row['id'] for row in evaluation
              if geometry(row['task']) in train_order or positions_geometry(row['task']) in train_position]
    if leaked:
        raise ValueError('评估题与训练集重叠 %d 条，禁止使用' % len(leaked))
    # 验证集只从训练分片里按摘要采样，评估分片完全不参与训练与选模。
    ordered = sorted(train, key=lambda row: hashlib.sha256(('validation:' + row['id']).encode()).hexdigest())
    validation = ordered[:args.validation_size]
    validation_ids = {row['id'] for row in validation}
    args.output.mkdir(parents=True, exist_ok=True)
    cases = [requirement(row, row['split']) for row in evaluation]
    write_json(args.output / 'eval-tasks.json', dict(
        source=str(args.database), protocol='curriculum_v3_requirement_only_v1',
        cases=cases, case_count=len(cases),
        cohorts=dict(collections.Counter(case['cohort'] for case in cases)),
        note='题目来自新课程 development 与 heldout 分片，只提供目标点、时序与允许厚度；参考结构不参与生成。'))
    write_json(args.output / 'train-index.json', dict(
        train=[row['id'] for row in train if row['id'] not in validation_ids],
        validation=sorted(validation_ids), validation_size=len(validation_ids),
        eval_ids=[case['id'] for case in cases],
        overlap_checked=dict(train_records=len(train), evaluation_records=len(cases), leaked=0)))
    bands = collections.Counter('%d目标%d时序%d格' % (len(case['task']['targets']),
                              len({t['order'] for t in case['task']['targets']}),
                              case['task']['depth']) for case in cases)
    print(json.dumps(dict(train=len(train), validation=len(validation_ids), evaluation=len(cases),
                          bands=dict(sorted(bands.items(), key=lambda item: -item[1])[:12])), ensure_ascii=False))


if __name__ == '__main__':
    main()
