"""合并新课程与过滤后的旧课程，生成续训用数据集。"""

import argparse
import collections
import hashlib
import json
import sqlite3
from pathlib import Path

from ...domain_rules import proposal_issues
from ...serialization import digest, write_json
from .config import OUTPUT

DEFAULT_OUTPUT = Path('data/generation/curriculum-mixed-legacy-arch')
OLD_SOURCE = Path('data/generation/stage4-accelerated/examples.jsonl')


def load_new(database):
    """读取新课程全部已验收结构，包含开发与保留分片。"""
    uri = 'file:%s?mode=ro' % Path(database).resolve()
    db = sqlite3.connect(uri, uri=True)
    try:
        rows = [json.loads(body) for (body,) in db.execute('SELECT body FROM records ORDER BY id')]
    finally:
        db.close()
    return [dict(id=row['id'], task=row['task'], proposal=row['proposal'],
                 family=row.get('family', ''), group=row.get('group', ''),
                 origin='new_curriculum') for row in rows]


def load_old(source):
    """读取旧课程拟合分片并排除两类侦测端顶推禁忌。"""
    kept, dropped, reasons = [], 0, collections.Counter()
    with Path(source).open() as handle:
        for line in handle:
            row = json.loads(line)
            if row.get('usage') != 'fit':
                continue
            issues = proposal_issues(row['proposal'])
            if issues:
                dropped += 1
                for issue in issues:
                    reasons['紧贴顶推' if issue['air_gap'] == 0 else '隔一格顶推'] += 1
                continue
            kept.append(dict(id=row['id'], task=row['task'], proposal=row['proposal'],
                             family=row.get('family', ''), group=row.get('group', ''),
                             origin='old_curriculum'))
    return kept, dropped, dict(reasons)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=OUTPUT/'records.sqlite3')
    parser.add_argument('--old-source', type=Path, default=OLD_SOURCE)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--validation-size', type=int, default=256)
    args = parser.parse_args()
    new = load_new(args.database)
    old, dropped, reasons = load_old(args.old_source)
    combined, seen = [], set()
    duplicates = 0
    for row in [*new, *old]:
        key = digest([row['task'], row['proposal']])
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        combined.append(row)
    ordered = sorted(combined, key=lambda row: hashlib.sha256(('validation:' + row['id']).encode()).hexdigest())
    validation_ids = {row['id'] for row in ordered[:args.validation_size]}
    for row in combined:
        row['split'] = 'validation' if row['id'] in validation_ids else 'train'
        row['usage'] = 'fit' if row['split'] == 'train' else 'validation'
    args.output.mkdir(parents=True, exist_ok=True)
    dataset = args.output/'dataset.jsonl'
    with dataset.open('w') as stream:
        for row in combined:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(',', ':')) + '\n')
    counts = collections.Counter(row['split'] for row in combined)
    origins = collections.Counter(row['origin'] for row in combined)
    plan = dict(sources=dict(new_curriculum=str(args.database), old_curriculum=str(args.old_source)),
                new_records=len(new), old_kept=len(old), old_dropped=dropped, old_drop_reasons=reasons,
                duplicates_removed=duplicates, records=len(combined), splits=dict(counts),
                origins=dict(origins), dataset_sha256=hashlib.sha256(dataset.read_bytes()).hexdigest(),
                protocol='curriculum_mixed_legacy_arch_dataset_v1',
                note='旧课程排除紧贴与隔一格顶推侦测端两类布局；新课程包含全部分片，因此此前167题评估集已进入训练。')
    write_json(args.output/'plan.json', plan)
    print(json.dumps(plan, ensure_ascii=False))


if __name__ == '__main__':
    main()
