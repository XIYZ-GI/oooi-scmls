"""有界连续派发与断点恢复；完成一个任务就补充一个任务。"""

from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
import json
import random
import time

from .config import CELLS, PENDING_PER_WORKER, SEED
from .worker import generate, initialize


def make_job(index, repository):
    rng = random.Random(f'{SEED}:schedule:{index}')
    weights = [max(.05, 1-repository.counts[f'train/{d}:{g}']/repository.goals[f'{d}:{g}'])
               for d, g in CELLS]
    d, g = rng.choices(CELLS, weights)[0]
    bands = [(s, t) for s in ('小截面', '中截面', '大截面')
             for t in ('2至5目标', '6至12目标', '13至32目标')]
    weights = [1/(1+repository.buckets[f'{d}:{g}/{s}/{t}'])**.5 for s, t in bands]
    s, t = rng.choices(bands, weights)[0]
    return (index, SEED, d, g, s, t)


def construct(repository, library, excluded, args, stopping):
    state = repository.state
    reasons = Counter(state['reasons'])
    started = time.monotonic()
    checkpoint_at = started
    report_at = state['attempts']
    export_at = state['attempts']
    replay = list(state.get('pending_jobs', []))
    state.update(run_start_records=sum(repository.counts.values()),
                 run_start_attempts=state['attempts'], workers=args.workers)
    with ProcessPoolExecutor(max_workers=args.workers, initializer=initialize,
                             initargs=(library, excluded)) as pool:
        pending = {}
        while True:
            permitted = (not stopping and not repository.complete()
                         and time.monotonic()-started < args.max_hours*3600)
            while permitted and len(pending) < args.workers*PENDING_PER_WORKER:
                if replay:
                    job = replay.pop(0)
                elif state['next_index'] < args.max_attempts:
                    job = make_job(state['next_index'], repository)
                    state['next_index'] += 1
                else:
                    break
                pending[pool.submit(generate, job)] = job
            state.update(pending_jobs=[*replay, *pending.values()], reasons=dict(reasons),
                         current_run_seconds=time.monotonic()-started)
            now = time.monotonic()
            if now-checkpoint_at >= 2 or not pending:
                report = repository.checkpoint(state, '正在构造' if pending else '已保存断点')
                checkpoint_at = now
                if state['attempts']-report_at >= 240:
                    print(json.dumps({k: report[k] for k in ('attempts', 'records', 'train_records',
                                     'skeletons', 'target_geometries', 'current_run_seconds')},
                                     ensure_ascii=False), flush=True)
                    report_at = state['attempts']
                if state['attempts']-export_at >= 2400:
                    repository.export()
                    export_at = state['attempts']
            if not pending:
                break
            completed, _ = wait(pending, timeout=1, return_when=FIRST_COMPLETED)
            for future in completed:
                result = future.result()
                pending.pop(future)
                reason = result['reason']
                if not reason:
                    reason = repository.add(result['row'])
                elif 'failed' in result:
                    repository.db.execute('INSERT OR IGNORE INTO failures VALUES (?,?)',
                        (reason, json.dumps(result, ensure_ascii=False)))
                reasons[reason] += 1
                state['attempts'] += 1
    return state
