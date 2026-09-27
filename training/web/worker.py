"""单个生成任务的 CPU 推理进程；取消时可以被立即终止，已有记录保留。"""

from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import json
import os
import secrets
import sys
import torch

from ..serialization import write_json
from ..inference import load_model
from . import repository as repo
from . import registry
from .config import PROTOCOL, SAMPLED_PROTOCOL, SAMPLING_TEMPERATURE, STORE


def save_replay(job_id, index, task, proposal):
    from ..evaluator import evaluate
    result = evaluate(task, proposal, capture=True)
    path = STORE/job_id/f'replay-{index}.json.gz'
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    with gzip.open(temporary, 'wt', compresslevel=1) as handle:
        json.dump(result, handle, ensure_ascii=False)
    temporary.replace(path)
    return result


def run(job_id):
    from .candidates import generate_candidates
    from ..evaluator import evaluate
    from ..load_placement import align_targets
    from ..task import validate_task
    job = repo.get_job(job_id)
    task = validate_task(job['task'])
    count = job['candidate_count']
    # 前八个候选必须可复现，因此固定种子；额外候选按概率采样，种子随结果保存。
    seed = secrets.randbits(32) if count > 8 else 41
    entry = registry.get(job.get('model_id'))
    path = registry.path_for(entry)
    repo.update(job_id, progress=1, message='正在加载'+entry['name'])
    if not entry['ready']:
        raise ValueError('模型尚未就绪或已禁用')
    if hashlib.sha256(path.read_bytes()).hexdigest() != entry['checkpoint_sha256']:
        raise ValueError('模型文件摘要与已注册版本不一致')
    torch.set_num_threads(min(4, len(os.sched_getaffinity(0))))
    torch.set_num_interop_threads(1)
    model, _ = load_model(path, 'cpu')

    def progress(done, total):
        repo.update(job_id, progress=5+int(65*done/total), message=f'正在生成结构 {done}/{total}')

    proposals = generate_candidates(model, task, count, seed, progress)
    repo.update(job_id, progress=72, message='正在按本列前端摆放负载并模拟')
    # 负载按该候选结构本列最前方块 +2 摆放，与打标器、评估脚本口径一致。
    load_tasks = [align_targets(task, proposal) for proposal in proposals]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda item: evaluate(item[0], item[1]), zip(load_tasks, proposals)))
    accepted = next((i for i, value in enumerate(results) if value['accepted']), None)
    # 没有完整通过时优先展示半通过候选：负载确实被推动，只是时序分组不合格。
    partial = next((i for i, value in enumerate(results) if value.get('partial')), None)
    selected = accepted if accepted is not None else partial if partial is not None else 0
    value = {'task': task, 'proposals': proposals, 'evaluations': results, 'load_tasks': load_tasks,
             'selected': selected, 'accepted': accepted is not None,
             'partial': partial is not None, 'checkpoint_sha256': entry['checkpoint_sha256'],
             'model_id': entry['id'], 'model_name': entry['name'], 'architecture': entry['architecture'],
             'sampling_protocol': SAMPLED_PROTOCOL if count > 8 else PROTOCOL,
             'sampling_seed': seed, 'sampling_temperature': SAMPLING_TEMPERATURE if count > 8 else 0,
             'device': 'cpu', 'candidate_budget': count}
    write_json(STORE/job_id/'result.json', value)
    repo.update(job_id, progress=95, message='正在保存运行回放')
    save_replay(job_id, selected, load_tasks[selected], proposals[selected])
    repo.update(job_id, status='success' if accepted is not None else 'not_found', progress=100,
                message='已找到完整通过的结构' if accepted is not None else
                        '未完整通过；已优先展示半通过候选（负载可推动，时序分组不满足）' if partial is not None else
                        f'{count}个候选均未完整通过，可查看结构与失败原因')


if __name__ == '__main__':
    try:
        run(sys.argv[1])
    except Exception as error:
        repo.update(sys.argv[1], status='error', message='生成失败：'+str(error)[:300])
        raise
