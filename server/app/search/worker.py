import logging
import os
import random
import time

from .evaluator import evaluate
from .learning import fit_model, predict
from .mutations import features, metrics, propose
from .repository import search_repository as repository
from .seeds import digest


def advance(job):
    stats = {s["seed_id"]: s["attempted"] for s in repository.stats(job["id"])}
    remaining = [s for s in job["seeds"] if stats.get(s["id"], 0) < job["config"]["per_seed"]]
    if not remaining:
        if not (job["model"] or {}).get("external"):
            repository.update(job["id"], model=fit_model(job, repository.training_records(job["id"])))
        repository.finish(job["id"])
        return
    seed = min(remaining, key=lambda s: stats.get(s["id"], 0))
    history, elite = repository.search_inputs(job["id"], seed["id"])
    rng = random.Random(f"{job['config']['random_seed']}:{seed['id']}:{len(history)}")
    original = {"blocks": seed["request"]["blocks"], "push": seed["request"]["push_point"]}
    parent = rng.choice([original, *elite])
    seen = {r["hash"] for r in history} | {digest([original["blocks"], original["push"]])}
    proposals = []
    for _ in range(400):
        candidate = propose(seed, parent, rng)
        if candidate and candidate["hash"] not in seen:
            proposals.append((candidate, features(seed, parent, candidate)))
            seen.add(candidate["hash"])
        if len(proposals) >= 8:
            break
    if not proposals:
        repository.update(job["id"], state="paused", error=f"{seed['name']} 的当前修改邻域已耗尽，可增加新样本后新建任务")
        return
    # 留出来源不使用学习模型挑选，避免反馈进入评估采样。
    guided = seed["split"] == "train" and rng.random() >= 0.3
    proposal, vector = max(proposals, key=lambda p: predict(job["model"], p[1])) if guided else rng.choice(proposals)
    try:
        result = evaluate(seed, proposal, job["config"]["rounds"])
    except Exception as error:
        logging.exception("候选模拟异常")
        result = {"accepted": False, "load_pass": False, "reason": str(error), "error": type(error).__name__, "rounds": []}
    improved = result["accepted"] and metrics(proposal["blocks"]) < metrics(original["blocks"])
    repository.save(job["id"], seed["id"], proposal, result, vector, improved)
    count = sum(stats.values()) + 1
    if count % 50 == 0 and not (job["model"] or {}).get("external"):
        repository.update(job["id"], model=fit_model(job, repository.training_records(job["id"])))
    logging.info("任务 %s：%s，第 %s 个候选，通过=%s，改进=%s", job["id"], seed["name"], len(history) + 1, result["accepted"], improved)


def run_worker(stop):
    logging.basicConfig(level=logging.INFO)
    # 独立进程运行，网页断开不影响任务；进程退出时在途候选由固定随机种子重做。
    try:
        os.nice(10)
    except OSError:
        pass
    while not stop.is_set():
        job_id = None
        try:
            job_id = repository.claim()
            if job_id:
                advance(repository.get(job_id))
            else:
                stop.wait(2)
        except Exception as error:
            logging.exception("搜索任务已暂停")
            if job_id:
                repository.update(job_id, state="paused", error=str(error))
            stop.wait(2)
        time.sleep(0.02)
