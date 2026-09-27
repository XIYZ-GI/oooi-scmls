"""移动线数据集结构生成器：有界采样、覆盖调度和可恢复保存。"""

import argparse
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
import fcntl
import json
import math
from pathlib import Path
import signal
import time

from ..serialization import digest, write_json
from .config import CATEGORIES, DEPTHS, NAME, OUTPUT, VERSION
from .repository import Repository
from .worker import generate
from .runtime import engine_identity


def run(args):
    cells = [(c, d) for c in args.categories for d in args.depths]
    base, extra = divmod(args.count, len(cells))
    quota = {key: base+int(i < extra) for i, key in enumerate(cells)}
    sources = {p.name: p.read_text() for p in Path(__file__).parent.glob('*.py')}
    if getattr(args, 'regular_growth', False) or any(depth > 4 for depth in args.depths):
        # 形态度量复用模块也参与批次身份，修改后不能混写旧数据目录。
        sources.update({'regular_generator_v2/'+p.name: p.read_text()
                        for p in (Path(__file__).parent.parent/'regular_generator_v2').glob('*.py')})
    identity = dict(version=VERSION, source_digest=digest(sources), engine=engine_identity(), seed=args.seed,
                    count=args.count, categories=args.categories, depths=args.depths,
                    min_targets=args.min_targets, min_density=args.min_density,
                    min_long_side=args.min_long_side, min_short_side=args.min_short_side,
                    min_extensions=args.min_extensions, extension_share=args.extension_share,
                    extension_placement=args.extension_placement, min_saturated_extensions=args.min_saturated_extensions,
                    search_mode=args.search_mode, simulation_budget=args.simulation_budget)
    identity['regular_growth'] = getattr(args, 'regular_growth', False)
    identity['feedback_growth'] = getattr(args, 'feedback_growth', 'mixed')
    if identity['regular_growth']:
        identity['solid_timing'] = getattr(args, 'solid_timing', 'balanced')
    repo = Repository(args.output, identity, batch_size=args.save_batch_size)
    write_json(args.output/'source.json',sources)
    running, submitted, interrupted = Counter(), set(repo.completed), [False]
    running_extensions = Counter()
    extension_quota = {key: math.ceil(n*args.extension_share)
                       if key[0] != '多目标同推' and key[1] <= 4 else 0 for key,n in quota.items()}
    original = {}
    for sig in (signal.SIGTERM, signal.SIGINT):
        original[sig] = signal.signal(sig, lambda *_: interrupted.__setitem__(0, True))
    next_index = 0
    last_report = time.monotonic()
    try:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            pending = {}
            while True:
                while len(pending) < args.workers*2 and len(submitted) < args.attempts and not interrupted[0]:
                    eligible = [key for key in cells if repo.counts[key]+running[key] < quota[key]]
                    if not eligible:
                        break
                    key = min(eligible, key=lambda k: ((repo.counts[k]+running[k])/max(1, quota[k]), cells.index(k)))
                    while next_index in submitted:
                        next_index += 1
                    # 大目标尝试独立记录；不会为了通过而删掉需求中的失败目标。
                    dense = args.min_density >= .35 or args.min_targets >= 13 or next_index % 5 != 0
                    need_extension = repo.extension_counts[key]+running_extensions[key] < extension_quota[key]
                    options = dict(search=args.search_mode == 'guided', simulation_budget=args.simulation_budget,
                                   min_long_side=args.min_long_side, min_short_side=args.min_short_side,
                                   min_extensions=max(args.min_extensions, int(need_extension)),
                                   extension_placement=args.extension_placement,
                                   min_saturated_extensions=args.min_saturated_extensions)
                    if getattr(args, 'regular_growth', False):
                        from .regular_options import options_for
                        options.update(options_for(next_index, key[1], args.solid_timing))
                    mode = getattr(args, 'feedback_growth', 'mixed')
                    if mode != 'off' and key[1] in (4, 5, 6) and options['search']:
                        from .feedback_options import options_for as feedback_options
                        options.update(feedback_options(next_index, mode, depth=key[1]))
                    job = (next_index, args.seed, *key, dense, args.min_targets, args.min_density, options)
                    pending[pool.submit(generate, job)] = (next_index, key, need_extension)
                    running_extensions[key] += int(need_extension)
                    submitted.add(next_index)
                    running[key] += 1
                if not pending:
                    break
                finished, _ = wait(pending, timeout=1, return_when=FIRST_COMPLETED)
                for future in finished:
                    index, key, need_extension = pending.pop(future)
                    running[key] -= 1
                    running_extensions[key] -= int(need_extension)
                    try:
                        result = future.result()
                    except Exception as error:
                        raise RuntimeError(f'候选 {index} 执行异常，未计为普通构造失败') from error
                    repo.save(result, quota)
                repo.flush_due()
                if time.monotonic()-last_report > 10:
                    report = repo.report('构造中', quota, export_records=False)
                    print(json.dumps({k: report[k] for k in ('status', 'attempts', 'accepted')}, ensure_ascii=False), flush=True)
                    last_report = time.monotonic()
        complete = all(repo.counts[key] >= quota[key] and repo.extension_counts[key] >= extension_quota[key]
                       for key in cells)
        status = '本批覆盖完成' if complete else ('已暂停' if interrupted[0] else '尝试预算用尽，覆盖未完成')
        report = repo.report(status, quota)
        print(json.dumps(report, ensure_ascii=False), flush=True)
        return 0 if complete else 2
    finally:
        for sig, handler in original.items():
            signal.signal(sig, handler)
        repo.close()


def main():
    parser = argparse.ArgumentParser(description=NAME)
    parser.add_argument('--output', type=Path, default=OUTPUT/'preview')
    parser.add_argument('--count', type=int, default=54)
    parser.add_argument('--attempts', type=int, default=1800)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--save-batch-size', type=int, default=32, help='每个事务最多保存的尝试数，每秒及退出时也提交')
    parser.add_argument('--seed', type=int, default=2026092309)
    parser.add_argument('--min-targets', type=int, default=3, help='每条结构的目标数量下限')
    parser.add_argument('--min-density', type=float, default=0, help='目标数量除以实际截面面积的下限')
    parser.add_argument('--min-long-side', type=int, default=0, help='实际截面长边下限，不填充空边')
    parser.add_argument('--min-short-side', type=int, default=0, help='实际截面短边下限')
    parser.add_argument('--min-extensions', type=int, default=0, help='每条至少包含的有效入口延伸拉驱数')
    parser.add_argument('--extension-placement',choices=('any','front','rear'),default='any',
                        help='按真实供电来源要求入口延伸拉驱前置或后置')
    parser.add_argument('--min-saturated-extensions',type=int,default=0,
                        help='至少包含多少处前端四输出已满的入口延伸')
    parser.add_argument('--extension-share', type=float, default=.7, help='推拉类别中入口延伸拉驱的最低配额比例')
    parser.add_argument('--search-mode', choices=('guided', 'legacy'), default='guided')
    parser.add_argument('--simulation-budget', type=int, default=64, help='单个候选的物理预筛次数上限')
    parser.add_argument('--regular-growth', action='store_true',
                        help='在原随机生长流程中组合同时推动实心区、推驱与拉驱随机支路')
    parser.add_argument('--feedback-growth', choices=('mixed', 'off', 'next_source', 'redstone_recall', 'half_engine'),
                        default='mixed', help='四至六格随机生长的跨组供电与活塞回收；混合保留原生长路线')
    parser.add_argument('--solid-timing', choices=('balanced', 'simultaneous', 'partitioned', 'either'),
                        default='balanced', help='规律专项的实心区：轮转两类、同刻、区内分时序、任一类型')
    parser.add_argument('--categories', nargs='+', choices=CATEGORIES, default=list(CATEGORIES))
    parser.add_argument('--depths', nargs='+', type=int, choices=DEPTHS)
    args = parser.parse_args()
    args.depths = args.depths or ([4] if args.regular_growth else [2, 3, 4])
    if args.regular_growth:
        if any(depth not in (4, 5, 6) for depth in args.depths):
            parser.error('规律分层构造支持四、五、六格实际厚度')
        args.search_mode = 'guided'
        args.categories = ['推拉结合多时序']
        args.min_density = max(.72, args.min_density)
        args.min_targets = max(15, args.min_targets)
        args.extension_share = 0
    if args.search_mode == 'legacy' and any(depth > 4 for depth in args.depths):
        parser.error('五、六格分层需要 guided 搜索模式')
    if min(args.count, args.attempts, args.workers, args.save_batch_size) < 1:
        parser.error('记录数、尝试预算和工作进程必须大于零')
    if not 3 <= args.min_targets <= 32 or not 0 <= args.min_density <= 1:
        parser.error('目标下限必须在3至32之间，密度必须在0至1之间')
    if not 0 <= args.extension_share <= 1 or not 0 <= args.min_extensions <= 8:
        parser.error('入口延伸比例须在零至一之间，数量须在零至八之间')
    if not 0 <= args.min_short_side <= 24 or not 0 <= args.min_long_side <= 24:
        parser.error('截面边长下限须在零至二十四之间')
    if not 1 <= args.simulation_budget <= 512:
        parser.error('物理预筛预算须在一至五百一十二之间')
    if not 0 <= args.min_saturated_extensions <= 8:
        parser.error('满位入口延伸数量须在零至八之间')
    if args.min_saturated_extensions and args.categories != ['推拉结合多时序']:
        parser.error('满位输出后继续拉驱仅适用于推拉结合多时序专项')
    if args.extension_placement != 'any' or args.min_saturated_extensions:
        args.min_extensions = max(args.min_extensions,args.min_saturated_extensions,1)
    if args.min_extensions and '多目标同推' in args.categories:
        parser.error('入口延伸拉驱的硬下限只适用于推拉类别')
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output/'.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error('该输出目录已有构造进程')
        return run(args)
