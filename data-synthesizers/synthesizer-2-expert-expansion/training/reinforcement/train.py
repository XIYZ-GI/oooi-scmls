"""分批GPU采样与CPU并行模拟的在策略PPO训练，支持完整断点恢复。"""

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import gzip
import json
import multiprocessing
from pathlib import Path
import random
import time

import torch

from ..data import read_examples
from ..inference import load_model
from ..serialization import write_json
from .assess import assess, file_sha
from .demands import DemandSampler
from .feedback import simulate
from .policy import ActorCritic
from .ppo import update
from .rollout import collect


def save(path, actor, policy, optimizer, sampler, iteration, best_score, best_iteration, full=False):
    value = {'model': actor.state_dict(), 'config': actor.config, 'step': iteration,
             'stage': 5, 'algorithm': 'ppo_terminal_mc_v1'}
    if full:
        value.update(critic=policy.value.state_dict(), optimizer=optimizer.state_dict(),
                     sampling_state=sampler.rng.getstate(), torch_rng=torch.get_rng_state(),
                     cuda_rng=torch.cuda.get_rng_state(), successes=sampler.successes,
                     best_score=best_score, best_iteration=best_iteration)
    temporary = path.with_suffix('.tmp')
    torch.save(value, temporary)
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description='第五阶段正式PPO训练')
    parser.add_argument('--data', default='data/generation/stage5')
    parser.add_argument('--output', default='runs/stage5')
    parser.add_argument('--plan', help='保留原计划，使用有记录的训练调整配置')
    args = parser.parse_args()
    root, output = Path(args.data), Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    (output/'rollouts').mkdir(exist_ok=True)
    plan = json.loads(Path(args.plan or root/'experiment-plan.json').read_text())
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.manual_seed(plan['seed'])
    actor, _ = load_model(plan['initial_checkpoint'], 'cuda')
    reference, _ = load_model(plan['initial_checkpoint'], 'cuda')
    reference.requires_grad_(False)
    policy = ActorCritic(actor).cuda().eval()
    optimizer = torch.optim.AdamW(policy.parameters(), lr=plan['learning_rate'], weight_decay=0.0, fused=True)
    sampler = DemandSampler(read_examples(root/'experts.jsonl'),
                            json.loads((root/'excluded-geometries.json').read_text()), plan['seed'],
                            plan.get('frontier_fraction', 0.0))
    development = read_examples(root/'development.jsonl')
    initial_step, best_score, best_iteration = 0, -1, 0
    if plan.get('warm_start') and not (output/'resume.pt').exists():
        warm = torch.load(plan['warm_start'], map_location='cuda', weights_only=True)
        actor.load_state_dict(warm['model']); policy.value.load_state_dict(warm['critic'])
        sampler.successes = warm['successes']
        sampler.rng.setstate(warm['sampling_state'])
    if (output/'resume.pt').exists():
        saved = torch.load(output/'resume.pt', map_location='cuda', weights_only=True)
        actor.load_state_dict(saved['model']); policy.value.load_state_dict(saved['critic'])
        optimizer.load_state_dict(saved['optimizer'])
        sampler.rng.setstate(saved['sampling_state']); sampler.successes = saved['successes']
        torch.set_rng_state(saved['torch_rng'].cpu()); torch.cuda.set_rng_state(saved['cuda_rng'].cpu())
        initial_step, best_score, best_iteration = saved['step'], saved['best_score'], saved['best_iteration']
        print(json.dumps({'恢复迭代': initial_step}, ensure_ascii=False), flush=True)
    elif (output/'run.json').exists():
        raise ValueError('已有运行但缺少断点，禁止覆盖')
    else:
        write_json(output/'run.json', {'plan': plan, 'actor_parameters': actor.parameter_report(),
            'critic_parameters': sum(p.numel() for p in policy.value.parameters()),
            'initial_sha256': file_sha(plan['initial_checkpoint']), 'torch': str(torch.__version__),
            'warm_start_sha256': file_sha(plan['warm_start']) if plan.get('warm_start') else None,
            'critic_backbone_gradient': False,
            'gpu': torch.cuda.get_device_name(), 'precision': 'float32_tf32',
            'code_sha256': {str(p): file_sha(p) for p in Path('training').rglob('*.py')},
            'note': '直接采样完整结构；终局实际模拟奖励；无专家结构监督损失、无人工构造模板。'})
    started = time.monotonic()
    with ProcessPoolExecutor(max_workers=plan['workers'], mp_context=multiprocessing.get_context('spawn')) as pool:
        if initial_step == 0:
            report = assess(actor, development, pool, output/'development-0')
            best_score = report['successes']
            save(output/'best.pt', actor, policy, optimizer, sampler, 0, best_score, 0)
            print(json.dumps({'迭代': 0, '开发集': report}, ensure_ascii=False), flush=True)
        with (output/'metrics.jsonl').open('a') as metrics:
            for iteration in range(initial_step+1, plan['iterations']+1):
                tick = time.monotonic()
                repeats = plan.get('rollouts_per_demand', 1)
                demands = [row for row in sampler.sample(plan['rollouts']//repeats) for _ in range(repeats)]
                pending = []
                for start in range(0, len(demands), plan['generation_batch']):
                    samples = collect(policy, demands[start:start+plan['generation_batch']], plan['temperature'])
                    pending.extend((row, pool.submit(simulate, {'task': row['task'], 'proposal': row['proposal']})) for row in samples)
                rows = []
                for row, future in pending:
                    row.update(future.result())
                    rows.append(row)
                    if row['evaluation']['accepted']:
                        sampler.add_success(row['task'])
                rollout_seconds = time.monotonic()-tick
                stats = update(policy, reference, optimizer, rows, plan, random.Random(plan['seed']+iteration))
                with gzip.open(output/'rollouts'/f'{iteration:05d}.jsonl.gz', 'wt', compresslevel=1) as handle:
                    for row in rows:
                        handle.write(json.dumps({k: v for k, v in row.items() if not k.startswith('old_')}, ensure_ascii=False)+'\n')
                row = {'iteration': iteration, 'samples': len(rows),
                       'successes': sum(r['evaluation']['accepted'] for r in rows),
                       'mean_reward': sum(r['reward'] for r in rows)/len(rows),
                       'success_pool': len(sampler.successes), 'sources': dict(Counter(r['source'] for r in rows)),
                       'success_by_source': dict(Counter(r['source'] for r in rows if r['evaluation']['accepted'])),
                       'reasons': dict(Counter(r['evaluation']['reason'] for r in rows)),
                       'rollout_seconds': rollout_seconds, 'seconds': time.monotonic()-tick,
                       'elapsed_seconds': time.monotonic()-started, **stats}
                metrics.write(json.dumps(row, ensure_ascii=False)+'\n'); metrics.flush()
                print(json.dumps(row, ensure_ascii=False), flush=True)
                ending = time.monotonic()-started >= plan['max_training_seconds'] or iteration == plan['iterations']
                if iteration % plan['validation_interval'] == 0 or ending:
                    report = assess(actor, development, pool, output/f'development-{iteration}')
                    if report['successes'] > best_score:
                        best_score, best_iteration = report['successes'], iteration
                        save(output/'best.pt', actor, policy, optimizer, sampler, iteration, best_score, best_iteration)
                    print(json.dumps({'迭代': iteration, '开发集': report, '最佳迭代': best_iteration}, ensure_ascii=False), flush=True)
                if iteration % plan['checkpoint_interval'] == 0 or ending:
                    save(output/f'checkpoint-{iteration}.pt', actor, policy, optimizer, sampler, iteration, best_score, best_iteration)
                    save(output/'resume.pt', actor, policy, optimizer, sampler, iteration, best_score, best_iteration, full=True)
                if ending:
                    break
    save(output/'last.pt', actor, policy, optimizer, sampler, iteration, best_score, best_iteration)
    write_json(output/'training-summary.json', {'iterations': iteration, 'best_iteration': best_iteration,
        'best_development_successes': best_score, 'seconds': time.monotonic()-started,
        'success_pool': len(sampler.successes), 'actor_sha256': file_sha(output/'best.pt'),
        'gpu_peak_bytes': torch.cuda.max_memory_allocated(), 'completed_planned_iterations': iteration == plan['iterations']})


if __name__ == '__main__':
    main()
