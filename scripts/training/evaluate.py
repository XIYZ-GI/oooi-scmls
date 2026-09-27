"""四套百题评估：八视角确定性生成，判定口径与网页推理页完全一致。

四套题各 100 道，内部键与展示名见 ``scripts/evaluation_sets.py``：

======================  ==================
内部键                  展示名
======================  ==================
``historical188``       基础航械题
``historical200``       简单航械题
``previous300``         普通航械题
``today100``            普通航械题-2
======================  ==================

每道题生成八个候选（截面等距变换 × 翻转，确定性、无采样），判定「连续三轮、
每列目标推过十块负载」。逐题结果落盘后中断重跑会直接复用，不会重复模拟。
"""

import argparse
import hashlib
import json
import multiprocessing
import os
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path
import time

import torch

from training.accelerated.symmetry import PROTOCOL, generate_symmetric
from training.evaluator import evaluate
from training.inference import load_model
from training.load_placement import align_targets
from training.serialization import digest, write_json

from scripts.evaluation_sets import COMBINED_NAME, ORDER, name
from .config import CANDIDATES, SEED, SUITES

# 与训练同一口径的注意力预算：批内候选数 × 最长工作区² 不超过这个值。
CELL_BUDGET = 8_000_000
# 一批最多几道题；实际还受上面预算约束，大网格会自动退化成更小的批。
GROUP_SIZE = 8
# 同一批里最长工作区不超过最短的这么多倍，避免小网格被大网格的补齐拖慢。
VOLUME_BAND = 1.3


def volume(task):
    return task["width"] * task["height"] * task["depth"]


def groups(cases, candidates, budget=CELL_BUDGET, size=GROUP_SIZE):
    """按体积切批：同批体积接近、补齐浪费最小，并满足注意力预算。"""
    chunk = []
    for case in sorted(cases, key=lambda item: volume(item["task"])):
        longest = max(volume(item["task"]) for item in (*chunk, case))
        band = VOLUME_BAND * volume(chunk[0]["task"]) if chunk else 0
        if chunk and (len(chunk) >= size or longest > band
                      or len(chunk + [case]) * candidates * longest * longest > budget):
            yield chunk
            chunk = [case]
        else:
            chunk = chunk + [case]
    if chunk:
        yield chunk


def judge(item):
    """多进程判定单元；负载按候选结构本列最前方块 +2 摆放。"""
    task, proposal = item
    return evaluate(align_targets(task, proposal), proposal)


def plan_of(cases, checkpoint, suite, candidates):
    return dict(checkpoint_sha256=hashlib.sha256(Path(checkpoint).read_bytes()).hexdigest(),
                tasks_sha256=digest(cases), candidates=candidates, sampling_protocol=PROTOCOL,
                temperature=0.0, seed=SEED, suite=suite,
                primary="现行领域标准（与网页推理判定一致）",
                load_placement="column_front_plus_2", driver="批量化并行评估")


def summarize(rows, cases, suites=ORDER):
    detail = {}
    for suite in suites:
        picked = [row for row in rows if row["id"].startswith(f"{suite}-")]
        if not picked:
            continue
        detail[name(suite)] = dict(
            tasks=len(picked), passed=sum(1 for row in picked if row["passed"]),
            candidates=sum(len(attempt["metrics"]) for row in picked for attempt in row["attempts"]),
            failure_reasons=_reasons(picked))
    total = sum(item["tasks"] for item in detail.values())
    passed = sum(item["passed"] for item in detail.values())
    return dict(overall=dict(tasks=total, passed=passed, suites=len(detail)),
                pass_rate=passed / total if total else None, detail=detail)


def _reasons(rows):
    counts = {}
    for row in rows:
        for attempt in row["attempts"]:
            for metric in attempt["metrics"]:
                if not metric["accepted"]:
                    counts[metric["reason"]] = counts.get(metric["reason"], 0) + 1
    return counts


def evaluate_suite(checkpoint, model_id, suite, benchmarks, output, workers, candidates, device, name_map=None):
    cases = json.loads((Path(benchmarks) / f"{suite}.json").read_text())
    directory = Path(output) / "evaluation" / model_id / suite
    directory.mkdir(parents=True, exist_ok=True)
    plan = plan_of(cases, checkpoint, suite, candidates)
    write_json(directory / "plan.json", plan)

    rows, pending = [], []
    for case in cases:
        path = directory / f"{case['id']}.json"
        if path.exists():
            row = json.loads(path.read_text())
            if row.get("plan_digest") != digest(plan):
                raise ValueError(f"{case['id']} 的旧结果与当前权重或协议不一致，请先移走旧目录")
            rows.append(row)
        else:
            pending.append(case)
    started = time.monotonic()

    def progress():
        value = dict(suite=suite, registry=name(suite), model=model_id, evaluated=len(rows),
                     total=len(cases), passed=sum(1 for row in rows if row["passed"]),
                     seconds=round(time.monotonic() - started))
        write_json(directory / "progress.json", value)
        print(json.dumps(value, ensure_ascii=False), flush=True)

    progress()
    if pending:
        model, _ = load_model(checkpoint, device)
        chunks = list(groups(pending, candidates))

        def prepare(chunk):
            proposals = generate_symmetric(model, [dict(task=case["task"]) for case in chunk],
                                           device, candidates, SEED)
            return list(zip(chunk, proposals))

        # 一个线程预取下一批候选，模拟进程池持续满载。
        with ThreadPoolExecutor(max_workers=1) as generator, \
                ProcessPoolExecutor(max_workers=workers,
                                    mp_context=multiprocessing.get_context("spawn")) as pool:
            ready = None
            for index, chunk in enumerate(chunks):
                work = ready.result() if ready is not None else prepare(chunk)
                ready = generator.submit(prepare, chunks[index + 1]) if index + 1 < len(chunks) else None
                items = [(case["task"], proposal) for case, proposals in work for proposal in proposals]
                results = list(pool.map(judge, items))
                offset = 0
                for case, proposals in work:
                    piece = results[offset:offset + len(proposals)]
                    offset += len(proposals)
                    row = dict(id=case["id"], cohort=case["cohort"],
                               category=(case.get("coverage") or {}).get("category"),
                               task=case["task"], plan_digest=digest(plan),
                               attempts=[dict(metrics=piece, proposals=proposals)],
                               passed=any(metric["accepted"] for metric in piece))
                    write_json(directory / f"{case['id']}.json", row)
                    rows.append(row)
                progress()
    report = summarize(rows, cases)
    report.update(plan=plan, seconds=time.monotonic() - started, workers=workers,
                  driver="批量化并行评估：一次生成多题候选，进程池持续满载")
    write_json(directory / "report.json", report)
    overall = report["overall"]
    print(json.dumps(dict(套=name(suite), 内部键=suite, 题数=overall["tasks"], 通过=overall["passed"],
                          秒=round(report["seconds"])), ensure_ascii=False), flush=True)
    return report


def combine(output, model_id, suites=ORDER):
    """把各套报告合并成「综合航械题」总览；缺套只记缺失，不报错。"""
    detail, missing, total, passed = {}, [], 0, 0
    for suite in suites:
        path = Path(output) / "evaluation" / model_id / suite / "report.json"
        if not path.exists():
            missing.append(name(suite))
            continue
        report = json.loads(path.read_text())
        overall = report["overall"]
        detail[name(suite)] = dict(tasks=overall["tasks"], passed=overall["passed"],
                                   seconds=report.get("seconds"))
        total += overall["tasks"]
        passed += overall["passed"]
    if not detail:
        return None
    value = dict(name=COMBINED_NAME, model=model_id, suites=list(detail), missing=missing,
                 tasks=total, passed=passed, pass_rate=passed / total if total else None, detail=detail)
    write_json(Path(output) / "evaluation" / model_id / "combined.json", value)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--model-id", required=True, help="结果目录名，通常与注册表里的版本编号一致")
    parser.add_argument("--suite", action="append", choices=SUITES)
    parser.add_argument("--benchmarks", default="benchmarks", help="四套百题 JSON 所在目录")
    parser.add_argument("--output", default="", help="实验结果目录，默认与权重同级的实验目录")
    parser.add_argument("--workers", type=int, default=min(32, (os.cpu_count() or 8) * 2),
                        help="模拟进程数；判定是纯 CPU 的，核越多越快")
    parser.add_argument("--candidates", type=int, default=CANDIDATES, choices=range(1, 9))
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    args = parser.parse_args()
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    torch.backends.cuda.matmul.allow_tf32 = False
    if args.device == "cuda" and not torch.cuda.is_available():
        raise SystemExit("指定了 --device cuda，但当前没有可用 GPU")
    output = args.output or str(Path(args.checkpoint).resolve().parent.parent)
    suites = tuple(args.suite or SUITES)
    for suite in suites:
        evaluate_suite(args.checkpoint, args.model_id, suite, args.benchmarks, output,
                       args.workers, args.candidates, args.device)
    if len(suites) > 1:
        value = combine(output, args.model_id)
        print(json.dumps({COMBINED_NAME: value}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
