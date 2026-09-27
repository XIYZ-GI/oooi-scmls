"""迁移同一生成器，按完整生成与混材运动共同选择检查点。"""

from collections import defaultdict
from copy import deepcopy
import argparse
import hashlib
import json
import math
import random
import time
from pathlib import Path

import torch

from ..data import collate, read_examples
from ..inference import load_model
from ..serialization import digest, write_json
from ..train import losses
from .config import DATA, RUNS
from .selection import validate_generation


def main():
    global DATA, RUNS
    parser = argparse.ArgumentParser(description='按完整生成表现执行一次有记录的迁移训练')
    parser.add_argument('--data', default=str(DATA))
    parser.add_argument('--output', default=str(RUNS))
    args = parser.parse_args()
    DATA, RUNS = Path(args.data), Path(args.output)
    plan = json.loads((DATA/'experiment-plan.json').read_text())
    if (RUNS/'run.json').exists():
        raise ValueError('已有训练运行，禁止覆盖原结果')
    RUNS.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(plan['seed'])
    torch.set_num_threads(4)
    torch.backends.cuda.matmul.allow_tf32 = True
    rng = random.Random(plan['seed'])
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model, initial = load_model(plan['initial_checkpoint'], device)
    families = defaultdict(lambda: defaultdict(list))
    for row in read_examples(DATA/'examples.jsonl'):
        if row['usage'] != 'fit':
            continue
        family = 'legacy' if row['family'].startswith('legacy_') else row['family']
        families[family][row['group']].append(row)
    for family in plan['family_sampling']:
        if not families[family]:
            raise ValueError('缺少训练课程：'+family)
    development = read_examples(DATA/'development.jsonl')
    optimizer = torch.optim.AdamW(model.parameters(), lr=plan['learning_rate'], weight_decay=0.01)
    run = {'plan': plan, 'parameters': model.parameter_report(), 'config': model.config,
           'initial_sha256': hashlib.sha256(Path(plan['initial_checkpoint']).read_bytes()).hexdigest(),
           'data_digest': digest((DATA/'examples.jsonl').read_text()),
           'development_digest': digest((DATA/'development.jsonl').read_text()),
           'heldout_digest': digest((DATA/'heldout.jsonl').read_text()),
           'code_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('training').rglob('*.py')},
           'torch': str(torch.__version__), 'gpu': torch.cuda.get_device_name() if device == 'cuda' else None,
           'transfer_fraction': 1.0, 'initial_step': initial['step']}
    write_json(RUNS/'run.json', run)
    started = time.monotonic()
    best, best_step = (-1, -1), 0
    validation_seconds = 0

    def save(name, step, score):
        path = RUNS/name
        torch.save({'model': model.state_dict(), 'config': model.config, 'step': step,
                    'seed': plan['seed'], 'data_sha256': run['data_digest'],
                    'generation_score': list(score)}, path.with_suffix('.tmp'))
        path.with_suffix('.tmp').replace(path)

    with (RUNS/'metrics.jsonl').open('w') as log:
        for step in range(plan['steps']+1):
            if step:
                model.train()
                family = rng.choices(list(plan['family_sampling']), weights=list(plan['family_sampling'].values()))[0]
                groups = list(families[family])
                subset = [rng.choice(families[family][rng.choice(groups)]) for _ in range(plan['batch_size'])]
                if plan.get('depth_slack_max', 0):
                    subset = deepcopy(subset)
                    for example in subset:
                        depth = example['task']['depth']
                        if depth < 4 and rng.random() < 0.5:
                            # 仅扩大允许空间；初始方块、负载、周期及全部物理行为相同。
                            example['task']['depth'] += rng.randint(1, min(plan['depth_slack_max'], 4-depth))
                rate = plan['learning_rate']*min(step/100, 1)*(0.15+0.85*0.5*(1+math.cos(math.pi*step/plan['steps'])))
                for g in optimizer.param_groups:
                    g['lr'] = rate
                loss, _, _ = losses(model, collate(subset, device))
                if not torch.isfinite(loss):
                    raise RuntimeError('训练损失非有限')
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                if step % 100 == 0:
                    row = {'step': step, 'family': family, 'loss': float(loss.detach()), 'seconds': time.monotonic()-started}
                    log.write(json.dumps(row)+'\n'); log.flush()
                    print(json.dumps(row), flush=True)
            if step % plan['validation_interval'] == 0 or step == plan['steps']:
                tick = time.monotonic()
                validation = validate_generation(model, development, device, plan['selection_candidates'])
                validation_seconds += time.monotonic()-tick
                write_json(RUNS/f'validation-{step}.json', validation)
                score = tuple(validation['score'])
                if score > best:
                    best, best_step = score, step
                    save('best.pt', step, score)
                save('last.pt', step, score)
                print(json.dumps({'step': step, 'generation_validation': validation['families'], 'best_step': best_step}, ensure_ascii=False), flush=True)
            if time.monotonic()-started > plan['max_training_seconds']:
                save('last.pt', step, best)
                break
    write_json(RUNS/'training-summary.json', {**run, 'completed_steps': step, 'best_step': best_step,
        'best_generation_score': best, 'seconds': time.monotonic()-started, 'validation_seconds': validation_seconds,
        'gpu_peak_bytes': torch.cuda.max_memory_allocated() if device == 'cuda' else 0})


if __name__ == '__main__':
    main()
