"""用真实 Lite 模型验证八视角、补齐、采样，并测量相同 CPU 上的解码耗时。"""

import argparse
import json
from pathlib import Path
from statistics import median
from time import perf_counter

import torch

from android.tools.export_model import DEFAULT_CHECKPOINT, build_model, verification_tasks
from training.accelerated.decoding import generate
from training.accelerated.symmetry import VARIANTS
from training.compact.transforms import transform
from training.data import batch_tasks
from training.serialization import decode_structure, positions


def transformed_tasks(task):
    """按服务器相同的顺序构造八个视角。"""
    return [transform({'task': task, 'proposal': {'blocks': [], 'push': dict(x=0, y=0, z=-2)}},
                      swap, sx, sy)['task'] for swap, sx, sy in VARIANTS]


def run(lite, model, tasks, temperature=0.0, dtype=torch.uint8):
    batch = batch_tasks(tasks, 'cpu', **model.feature_options)
    output = lite.run_method('generate', (batch['features'], batch['coords'],
                                         batch['padding'].to(dtype), float(temperature)))
    return [decode_structure(task, output[0][i, :len(positions(task))].tolist(), int(output[1][i]))
            for i, task in enumerate(tasks)]


def benchmark(lite, old, batch, threads, repeats):
    """相同输入、线程、解释器，预热后比较中位数；不包含模拟和回放。"""
    timings = {}
    torch.set_num_threads(threads)
    for name, module in [('旧版全序列', old), ('新版缓存', lite)]:
        module.run_method('generate', (*batch, 0.0))
        elapsed = []
        for _ in range(repeats):
            started = perf_counter()
            module.run_method('generate', (*batch, 0.0))
            elapsed.append(perf_counter() - started)
        timings[name] = round(median(elapsed), 4)
    timings['提速倍数'] = round(timings['旧版全序列'] / timings['新版缓存'], 2)
    return timings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--checkpoint', type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--repeats', type=int, default=3)
    args = parser.parse_args()
    torch.set_num_threads(args.threads)
    model, _, _ = build_model(args.checkpoint)
    lite = torch._C._load_for_lite_interpreter(str(args.model), None)
    tasks = verification_tasks(None)
    cases = 0
    with torch.inference_mode():
        for task in tasks:
            variants = transformed_tasks(task)
            reference = generate(model, variants, 'cpu')
            for dtype in (torch.bool, torch.uint8):
                # 安卓按内存上限分批；分别验证批量与串行结果。
                actual = []
                for offset in range(0, 8, 4):
                    actual.extend(run(lite, model, variants[offset:offset + 4], dtype=dtype))
                assert actual == reference, f'八视角结果不一致：{task}, {dtype}'
                assert run(lite, model, variants[:1], dtype=dtype) == reference[:1]
                cases += len(variants) + 1
            print(f"八视角一致：{task['width']}×{task['height']}×{task['depth']}", flush=True)

        reference = generate(model, tasks, 'cpu')
        assert run(lite, model, tasks) == reference, '混合长度补齐结果不一致'
        for seed in (41, 97):
            torch.manual_seed(seed)
            reference = generate(model, tasks[:2], 'cpu', temperature=0.7)
            torch.manual_seed(seed)
            assert run(lite, model, tasks[:2], temperature=0.7) == reference, '采样路径不一致'
        cases += 7
        largest = dict(tasks[-1], width=8, height=8, depth=8)
        assert run(lite, model, [largest]) == generate(model, [largest], 'cpu'), '512 格边界结果不一致'
        cases += 1
        print('补齐、采样与 512 格边界一致', flush=True)
        report = {'校验候选数': cases, '线程数': args.threads, '设备': '宿主机 CPU，非安卓真机', '耗时': {}}
        if args.baseline:
            old = torch._C._load_for_lite_interpreter(str(args.baseline), None)
            for task in tasks[1:]:
                batch = batch_tasks([task], 'cpu', **model.feature_options)
                inputs = (batch['features'], batch['coords'], batch['padding'].to(torch.uint8))
                size = f"{task['width']}×{task['height']}×{task['depth']}"
                report['耗时'][size] = benchmark(lite, old, inputs, args.threads, args.repeats)
                print(size, report['耗时'][size], flush=True)
        if args.output:
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
