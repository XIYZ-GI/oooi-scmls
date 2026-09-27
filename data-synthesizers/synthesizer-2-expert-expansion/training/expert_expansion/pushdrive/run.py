"""在服务器持续构造推驱优化课程；不启动模型训练。"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal

import mcscai_engine

from ...serialization import write_json
from .config import (CATEGORIES, LIMITS, OUTPUT, SEED, TOTAL_RECORDS, WORKERS)
from .repository import Repository
from .scheduling import construct


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--workers', type=int, default=WORKERS)
    parser.add_argument('--max-attempts', type=int, default=4000000)
    parser.add_argument('--max-hours', type=float, default=8)
    args = parser.parse_args()
    if args.workers < 1 or args.max_attempts < 1 or args.max_hours <= 0:
        parser.error('进程数、尝试预算和运行时限必须大于零')
    args.output.mkdir(parents=True, exist_ok=True)
    import fcntl
    lock = (args.output/'run.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    source = sorted(Path(__file__).parent.glob('*.py'))
    plan = dict(protocol='pushdrive_curriculum_v1', seed=SEED, total_records=TOTAL_RECORDS,
                categories=CATEGORIES, limits=LIMITS, engine_version=mcscai_engine.__version__,
                code={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source},
                status='推驱优化课程构造；不启动训练')
    path = args.output/'plan.json'
    if path.exists() and json.loads(path.read_text()) != plan:
        raise ValueError('代码、配置或引擎版本变化，必须使用新的输出目录')
    write_json(path, plan)
    repository = Repository(args.output)
    stopping = []
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, lambda *_: stopping.append(True))
    state = construct(repository, args, stopping)
    status = '课程数量已达标' if repository.complete() else (
        '收到停止信号，已保存断点' if stopping else '预算结束，覆盖尚未完成')
    report = repository.checkpoint(state, status)
    repository.export()
    if repository.complete():
        write_json(args.output/'construction-complete.json', report)
    print(json.dumps({k: report[k] for k in ('status', 'records', 'train_records', 'attempts',
                                             'category_progress')}, ensure_ascii=False), flush=True)
    repository.db.close()


if __name__ == '__main__':
    main()
