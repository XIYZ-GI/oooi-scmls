"""按累计工作进程耗时公平派发，困难专项不会阻塞其他专项。"""

import time
import traceback

from ..worker import generate


def execute(job):
    start = time.process_time()
    try:
        result = generate(job)
    except (MemoryError, OSError, ImportError):
        # 资源、文件和运行环境异常不能当成孤立候选失败继续运行。
        raise
    except Exception as error:
        result = dict(index=job[0], reason='候选执行异常，已隔离',
                      error=dict(kind=type(error).__name__, message=str(error),
                                 traceback=traceback.format_exc(), job=job))
    result['worker_cpu_seconds'] = time.process_time() - start
    return result


def choose(profiles, stats, running):
    eligible = [p for p in profiles if stats[p['id']]['accepted'] + running[p['id']] < p['quota']]
    if not eligible:
        return None

    def score(profile):
        s = stats[profile['id']]
        # 估计在途耗时，防止初始状态一次派发全部进程给同一专项。
        average = max(.05, s['cpu_seconds'] / s['attempts']) if s['attempts'] else .5
        return (s['cpu_seconds'] + running[profile['id']] * average) / profile['quota']

    return min(eligible, key=score)
