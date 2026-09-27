"""把当前条件覆盖课程导出为旧第四阶段架构可读的训练文件。"""

import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from pathlib import Path

from ...serialization import write_json
from .config import OUTPUT

DEFAULT_EXPORT = Path('data/generation/curriculum-v3-legacy-arch')


def load_rows(database):
    """只读读取课程数据库全部已验收结构。"""
    uri = 'file:%s?mode=ro' % Path(database).resolve()
    db = sqlite3.connect(uri, uri=True)
    try:
        return [json.loads(body) for (body,) in db.execute('SELECT body FROM records ORDER BY id')]
    finally:
        db.close()


def convert(row, split):
    """裁剪为训练脚本需要的字段，评估证据留在课程数据库里。"""
    return dict(id=row['id'], task=row['task'], proposal=row['proposal'], split=split,
                family=row.get('family', ''), group=row.get('group', ''),
                usage='fit' if split == 'train' else 'validation')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=OUTPUT / 'records.sqlite3')
    parser.add_argument('--output', type=Path, default=DEFAULT_EXPORT)
    parser.add_argument('--train-index', type=Path, default=DEFAULT_EXPORT / 'train-index.json')
    args = parser.parse_args()
    index = json.loads(args.train_index.read_text())
    validation_ids = set(index['validation'])
    eval_ids = set(index['eval_ids'])
    rows = load_rows(args.database)
    train = [convert(row, 'validation' if row['id'] in validation_ids else 'train')
             for row in rows if row['split'] == 'train' and row['id'] not in validation_ids | eval_ids]
    validation = [convert(row, 'validation') for row in rows if row['id'] in validation_ids]
    if not train or not validation:
        parser.error('训练或验证集合为空，不能开始训练')
    if any(row['id'] in eval_ids for row in [*train, *validation]):
        parser.error('评估题不能进入训练文件')
    args.output.mkdir(parents=True, exist_ok=True)
    dataset = args.output / 'dataset.jsonl'
    with dataset.open('w') as stream:
        for row in [*train, *validation]:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(',', ':')) + '\n')
    counts = Counter(row['split'] for row in [*train, *validation])
    plan = dict(source=str(args.database), protocol='curriculum_v3_legacy_arch_dataset_v2',
                records=len(train) + len(validation), splits=dict(counts),
                evaluation_tasks=len(eval_ids), evaluation_excluded=True,
                dataset_sha256=hashlib.sha256(dataset.read_bytes()).hexdigest(),
                note='训练只用 train 分片，评估题与验证集来自不同来源；旧第四阶段架构与参数规模不变。')
    write_json(args.output / 'plan.json', plan)
    print(json.dumps(plan, ensure_ascii=False))


if __name__ == '__main__':
    main()
