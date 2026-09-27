"""旧第四阶段架构在新课程上从零训练：长度分桶控制显存，损失与既有监督训练一致。"""

import argparse
import json
import math
from pathlib import Path
import random
import time

import torch

from ...data import collate, read_examples
from ...model import Generator
from ...serialization import digest, positions, write_json
from ...train import losses


def length(record):
    """需求网格的规范遍历长度，用于估计注意力和显存开销。"""
    return len(positions(record['task']))


def batches(records, rng, token_budget, max_batch, min_batch):
    """按长度相邻采样，使同一批的补齐浪费和注意力开销可控。"""
    ordered = sorted(records, key=length)
    lengths = [length(record) for record in ordered]
    while True:
        index = rng.randrange(len(ordered))
        batch_size = max(min_batch, min(max_batch, token_budget // max(1, lengths[index])))
        window = max(batch_size*3, 16)
        low, high = max(0, index-window), min(len(ordered), index+window+1)
        size = min(batch_size, high-low)
        yield [ordered[j] for j in rng.sample(range(low, high), size)]


def validate(model, records, device, batch_size=64):
    """按长度排序分批计算验证损失，不参与梯度。"""
    ordered = sorted(records, key=length)
    total, count = 0.0, 0
    model.eval()
    with torch.inference_mode():
        for start in range(0, len(ordered), batch_size):
            subset = ordered[start:start+batch_size]
            value, _, _ = losses(model, collate(subset, device))
            total += float(value) * len(subset)
            count += len(subset)
    return total / max(1, count)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--steps', type=int, default=6000)
    parser.add_argument('--token-budget', type=int, default=16384)
    parser.add_argument('--max-batch', type=int, default=192)
    parser.add_argument('--min-batch', type=int, default=8)
    parser.add_argument('--learning-rate', type=float, default=3e-4)
    parser.add_argument('--seed', type=int, default=20260922)
    parser.add_argument('--max-seconds', type=int, default=10800)
    parser.add_argument('--precision', choices=('bf16', 'fp32'), default='bf16')
    parser.add_argument('--threads', type=int, default=8)
    parser.add_argument('--resume', help='从已有检查点继续训练，只加载权重与优化器')
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(args.threads)
    torch.manual_seed(args.seed)
    random.seed(args.seed)
    rng = random.Random(args.seed)
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    if device == 'cuda':
        torch.backends.cuda.matmul.allow_tf32 = True
    records = read_examples(args.data)
    train = [row for row in records if row.get('split') == 'train']
    validation = [row for row in records if row.get('split') == 'validation']
    if not train or not validation:
        raise ValueError('训练或验证集合为空')
    model = Generator(width=192, heads=6, encoder_layers=4, decoder_layers=6).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=0.01)
    start_step = 0
    if args.resume:
        checkpoint = torch.load(args.resume, map_location=device, weights_only=True)
        if checkpoint.get('config') != model.config:
            raise ValueError('续训检查点的网络配置与当前架构不一致')
        model.load_state_dict(checkpoint['model'])
        if checkpoint.get('optimizer'):
            optimizer.load_state_dict(checkpoint['optimizer'])
        start_step = int(checkpoint.get('step', 0))
    run = dict(arguments=vars(args), start_step=start_step, config=model.config, parameters=model.parameter_report(),
               device=device, gpu=torch.cuda.get_device_name() if device == 'cuda' else None,
               torch=str(torch.__version__), precision=args.precision,
               train_examples=len(train), validation_examples=len(validation),
               data_sha256=digest(Path(args.data).read_text()),
               code_sha256={p.name: digest(p.read_text()) for p in Path('training').rglob('*.py')},
               protocol='curriculum_v3_legacy_arch_from_scratch_v1')
    write_json(output / 'run.json', run)
    print(json.dumps({k: run[k] for k in ('parameters', 'device', 'gpu', 'train_examples',
                                          'validation_examples', 'precision')}, ensure_ascii=False), flush=True)
    stream = batches(train, rng, args.token_budget, args.max_batch, args.min_batch)
    metrics = (output / 'metrics.jsonl').open('a')
    started, best, best_step = time.monotonic(), float('inf'), 0

    def save(path, step):
        torch.save(dict(model=model.state_dict(), optimizer=optimizer.state_dict(), config=model.config,
                        step=step, seed=args.seed, data_sha256=run['data_sha256'],
                        parameters=run['parameters'], protocol=run['protocol']), path)

    for step in range(start_step+1, args.steps+1):
        model.train()
        rows = next(stream)
        batch = collate(rows, device)
        warmup = 1.0 if start_step else min(step/100, 1)
        lr = args.learning_rate * warmup * (0.1 + 0.9*0.5*(1+math.cos(math.pi*step/args.steps)))
        for group in optimizer.param_groups:
            group['lr'] = lr
        if args.precision == 'bf16' and device == 'cuda':
            with torch.autocast('cuda', dtype=torch.bfloat16):
                loss, blocks, push = losses(model, batch)
        else:
            loss, blocks, push = losses(model, batch)
        if not torch.isfinite(loss):
            raise RuntimeError('训练损失不是有限值，停止并保留检查点')
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        if step % 50 == 0 or step == 1:
            row = dict(step=step, loss=float(loss.detach()), blocks=float(blocks.detach()),
                       push=float(push.detach()), lr=lr, seconds=time.monotonic()-started,
                       batch=len(rows), tokens=sum(length(r) for r in rows))
            metrics.write(json.dumps(row)+'\n')
            metrics.flush()
            print(json.dumps(row), flush=True)
        if step % 500 == 0 or step == args.steps:
            value = validate(model, validation, device)
            if value < best:
                best, best_step = value, step
                save(output/'best.pt', step)
            save(output/'last.pt', step)
            print(json.dumps(dict(step=step, validation=value, best=best, best_step=best_step),
                             ensure_ascii=False), flush=True)
        if time.monotonic()-started > args.max_seconds:
            save(output/'last.pt', step)
            print(json.dumps(dict(stopped='达到时间上限', step=step), ensure_ascii=False), flush=True)
            break
    if not (output/'last.pt').exists():
        save(output/'last.pt', args.steps)
    write_json(output/'training-summary.json', dict(best_validation_loss=best, best_step=best_step,
                                                    seconds=time.monotonic()-started, run=run))
    print(json.dumps(dict(best_validation_loss=best, best_step=best_step,
                          seconds=time.monotonic()-started), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
