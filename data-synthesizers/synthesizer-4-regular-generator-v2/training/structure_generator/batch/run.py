"""低优先级长期运行入口，信号停止时保存断点并收完在途结果。"""

import argparse
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
import fcntl
import json
import multiprocessing
from pathlib import Path
import shutil
import signal
import time

from ...serialization import digest, write_json
from ..runtime import engine_identity
from .profiles import job_for, profiles
from .reporting import report
from .scheduling import choose, execute
from .storage import Store


def initialize_worker():
    # 停止交由主进程处理，已经开始的有界候选完成后再退出。
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def run(args):
    if getattr(args, 'preset', 'legacy') == 'latest-mixed':
        from .mixed_profiles import profiles as mixed_profiles
        cells = mixed_profiles(args.count)
    else:
        cells = profiles(args.count)
    root = Path(__file__).resolve().parents[2]
    sources = {str(p.relative_to(root)): p.read_text() for p in sorted(root.rglob('*.py'))
               if 'tests' not in p.parts and '__pycache__' not in p.parts}
    engine = engine_identity()
    if not engine['native_preflight'] or not engine['native_snapshot']:
        raise RuntimeError('长期运行需要已优化的Rust预筛和原生快照接口')
    identity = dict(schema=1, source_digest=digest(sources), engine=engine,
                    seed=args.seed, profiles=cells, skeleton_limit=args.skeleton_limit)
    repo = Store(args.output, identity, cells, args.skeleton_limit)
    if not (args.output / 'source.json').exists():
        write_json(args.output / 'source.json', sources)
        write_json(args.output / 'identity.json', identity)
    stopping = [False]
    previous = {sig: signal.signal(sig, lambda *_: stopping.__setitem__(0, True))
                for sig in (signal.SIGTERM, signal.SIGINT)}
    status, pending, started, last_report = '构造中', {}, time.monotonic(), 0.
    replay = repo.pending()
    running = Counter(p for p, _ in replay)
    completed_session, accepted_session = 0, 0

    def progress():
        return report(repo, status, workers=args.workers, session_seconds=round(time.monotonic() - started, 1),
                      session_attempts=completed_session, session_accepted=accepted_session)

    try:
        with ProcessPoolExecutor(max_workers=args.workers, initializer=initialize_worker,
                                 mp_context=multiprocessing.get_context('spawn')) as pool:
            while True:
                if repo.consecutive_errors() >= 20:
                    status = '连续候选异常，已暂停'
                if stopping[0]:
                    status = '已暂停'
                if shutil.disk_usage(args.output).free < args.min_free_gib * 2**30:
                    status = '磁盘余量不足，已暂停'
                stats = repo.stats()
                if args.max_attempts and completed_session + len(pending) >= args.max_attempts:
                    status = '本次尝试预算已用尽'
                dispatch = []
                if status == '构造中':
                    while len(pending) + len(dispatch) < args.workers:
                        if args.max_attempts and completed_session + len(pending) + len(dispatch) >= args.max_attempts:
                            break
                        if replay:
                            profile_id, job = replay.pop(0)
                        else:
                            profile = choose(cells, stats, running)
                            if profile is None:
                                break
                            profile_id = profile['id']
                            job = repo.reserve(profile_id, lambda i: job_for(profile, i, args.seed))
                            running[profile_id] += 1
                        dispatch.append((profile_id, job))
                    # 任务必须先落盘再送工作进程；结果和新任务在同一事务中提交。
                    repo.db.commit()
                    for profile_id, job in dispatch:
                        pending[pool.submit(execute, job)] = (profile_id, job[0])
                if not pending:
                    if all(s['accepted'] >= p['quota'] for p in cells for s in (stats[p['id']],)):
                        status = '十万条目标完成' if args.count == 100000 else '目标完成'
                    break
                finished, _ = wait(pending, timeout=1, return_when=FIRST_COMPLETED)
                with repo.db:
                    for future in finished:
                        profile_id, index = pending.pop(future)
                        result = future.result()
                        if result['index'] != index:
                            raise ValueError('工作进程返回了错误的任务编号')
                        reason = repo.finish(profile_id, result)
                        if result.get('error'):
                            print(json.dumps(dict(warning=reason, index=index, profile=profile_id,
                                                  error=result['error']['kind'],
                                                  message=result['error']['message']), ensure_ascii=False), flush=True)
                            if repo.consecutive_errors() >= 20:
                                status = '连续候选异常，已暂停'
                        running[profile_id] -= 1
                        completed_session += 1
                        accepted_session += reason == '已保存'
                if time.monotonic() - last_report >= args.report_seconds:
                    value = progress()
                    print(json.dumps({k: value[k] for k in ('status', 'attempts', 'accepted', 'pending')},
                                     ensure_ascii=False), flush=True)
                    last_report = time.monotonic()
        value = progress()
        print(json.dumps({k: value[k] for k in ('status', 'attempts', 'accepted', 'pending')},
                         ensure_ascii=False), flush=True)
        return (4 if status.startswith('连续候选异常') else 3 if status.startswith('磁盘')
                else 2 if status.startswith('本次') else 0)
    except BaseException:
        repo.db.rollback()
        report(repo, '异常停止，待处理任务保留', workers=args.workers)
        raise
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
        repo.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--count', type=int, default=100000)
    parser.add_argument('--preset', choices=('legacy', 'latest-mixed'), default='legacy',
                        help='旧批次或三至六格红石、半动机、实心矩形混合批次')
    parser.add_argument('--workers', type=int, default=7)
    parser.add_argument('--seed', type=int, default=2026092201)
    parser.add_argument('--skeleton-limit', type=int, default=16)
    parser.add_argument('--min-free-gib', type=float, default=8.)
    parser.add_argument('--report-seconds', type=float, default=30.)
    parser.add_argument('--max-attempts', type=int, default=0, help='本次候选预算，零表示持续运行')
    args = parser.parse_args()
    if min(args.count, args.workers, args.skeleton_limit, args.report_seconds) <= 0:
        parser.error('数量、进程数、骨架上限、报告间隔必须为正')
    if min(args.min_free_gib, args.max_attempts) < 0:
        parser.error('磁盘余量和候选预算不能为负')
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / '.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error('该数据目录已有生成进程')
        return run(args)
