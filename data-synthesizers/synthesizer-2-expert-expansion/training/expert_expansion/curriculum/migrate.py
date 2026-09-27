"""在旧任务停止后复制已验收课程和断点，保留原版本及其冻结计划。"""

import argparse
import fcntl
import json
from pathlib import Path
import sqlite3

from ...serialization import digest, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    if not (args.source/'records.sqlite3').is_file():
        parser.error('来源数据库不存在')
    args.destination.mkdir(parents=True, exist_ok=True)
    with (args.source/'run.lock').open('a') as source_lock, (args.destination/'run.lock').open('a') as dest_lock:
        for lock in (source_lock, dest_lock):
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        destination = args.destination/'records.sqlite3'
        if destination.exists():
            parser.error('目标数据库已存在，禁止覆盖')
        original = sqlite3.connect(f'file:{args.source.resolve()}/records.sqlite3?mode=ro', uri=True)
        target = sqlite3.connect(destination)
        try:
            original.backup(target)
            plan = json.loads((args.source/'plan.json').read_text())
            ids = [r[0] for r in target.execute('SELECT id FROM records ORDER BY id')]
            write_json(args.destination/'inherited.json', dict(
                source=str(args.source.resolve()), records=len(ids), record_ids_sha256=digest(ids),
                source_plan=plan, note='继承记录沿用原版本验收证据；新增记录使用新版本冻结计划。'))
            print(json.dumps(dict(inherited_records=len(ids), destination=str(args.destination)), ensure_ascii=False))
        finally:
            target.close()
            original.close()


if __name__ == '__main__':
    main()
