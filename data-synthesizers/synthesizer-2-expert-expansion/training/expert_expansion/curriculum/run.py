"""在服务器持续构造分条件课程，保存覆盖缺口；不启动模型训练。"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal

import mcscai_engine

from ...reinforcement.demands import geometry
from ...serialization import digest, write_json
from ..config import ROOT
from .config import (OUTPUT, SEED, TRAIN_COUNT, HOLDOUT_PER_CELL, LIMITS,
                     EXACT_CAP, GEOMETRY_CAP, POSITION_CAP, SKELETON_CAP)
from .repository import Repository
from .scheduling import construct


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--workers', type=int, default=os.cpu_count() or 2)
    parser.add_argument('--max-attempts', type=int, default=2000000)
    parser.add_argument('--max-hours', type=float, default=12)
    args = parser.parse_args()
    if args.workers < 1 or args.max_attempts < 1 or args.max_hours <= 0:
        parser.error('进程数、尝试预算和运行时限必须大于零')
    args.output.mkdir(parents=True, exist_ok=True)
    # 文件锁防止两个服务同时使用同一断点写课程。
    import fcntl
    lock = (args.output/'run.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    library = json.loads((ROOT/'module-library.json').read_text())
    source_paths = list(Path(__file__).parent.glob('*.py'))
    source_paths += [Path('training/expert_expansion')/name for name in
                     ('admission.py', 'composition.py', 'modules.py', 'transport.py')]
    source_paths += [Path('training/evaluator.py'), Path('training/v2/foundation.py')]
    plan = dict(protocol='balanced_backtracking_curriculum_v3', seed=SEED, train_count=TRAIN_COUNT,
                holdout_per_cell=HOLDOUT_PER_CELL, limits=LIMITS,
                caps=dict(exact=EXACT_CAP, geometry=GEOMETRY_CAP, positions=POSITION_CAP, skeleton=SKELETON_CAP),
                library_sha256=digest(library['modules']), engine_version=mcscai_engine.__version__,
                code={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(source_paths)},
                status='课程构造已获授权；专家覆盖门槛和训练启动另行检查')
    path = args.output/'plan.json'
    if path.exists() and json.loads(path.read_text()) != plan:
        raise ValueError('代码、库或配置变化，必须使用新的输出目录，不能混用断点')
    write_json(path, plan)
    excluded_rows = json.loads((ROOT/'experts.json').read_text())
    reserved = ROOT/'reserved-cases.json'
    if reserved.exists():
        excluded_rows += json.loads(reserved.read_text())['cases']
    excluded = {geometry(r['task']) for r in excluded_rows}
    excluded.update(geometry({**r['task'], 'targets': [{**t, 'order': 1} for t in r['task']['targets']]})
                    for r in excluded_rows)
    repository = Repository(args.output, excluded)
    stopping = []
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, lambda *_: stopping.append(True))
    state = construct(repository, library, excluded, args, stopping)
    status = '课程数量已达标，等待覆盖审查和训练放行' if repository.complete() else (
        '收到停止信号，已保存断点' if stopping else '预算结束，覆盖尚未完成')
    report = repository.checkpoint(state, status)
    repository.export()
    if repository.complete():
        write_json(args.output/'construction-complete.json', report)
    print(json.dumps({k: report[k] for k in ('status', 'records', 'train_records', 'attempts')}, ensure_ascii=False), flush=True)
    repository.db.close()


if __name__ == '__main__':
    main()
