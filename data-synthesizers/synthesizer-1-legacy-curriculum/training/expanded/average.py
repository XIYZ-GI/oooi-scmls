"""用训练后期权重均值减少检查点波动，仅按开发完整运行表现选择。"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import time

import torch

from ..data import read_examples
from ..inference import load_model
from ..serialization import digest, write_json
from .selection import validate_generation


def main():
    parser = argparse.ArgumentParser(description='比较后期权重均值与原开发最优模型')
    parser.add_argument('--source', required=True)
    parser.add_argument('--data', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    source, data, output = map(Path, (args.source, args.data, args.output))
    if output.exists():
        raise ValueError('不覆盖已有模型平均实验')
    summary = json.loads((source/'training-summary.json').read_text())
    if summary['development_digest'] != digest((data/'development.jsonl').read_text()):
        raise ValueError('开发数据与原选模数据不同，不能复用原分数')
    steps = summary['completed_steps']
    if steps != summary['plan']['steps']:
        raise ValueError('训练提前结束，不执行预定后期平均')
    interval = summary['plan']['validation_interval']
    checkpoints = [source/f'checkpoint-{steps-i*interval}.pt' for i in range(4)]
    torch.set_num_threads(4)
    torch.backends.cuda.matmul.allow_tf32 = True
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    output.mkdir(parents=True)
    started = time.monotonic()
    average = None
    for path in checkpoints:
        checkpoint = torch.load(path, map_location='cpu', weights_only=True)
        if average is None:
            average = checkpoint
            average['model'] = {k: v.clone()/len(checkpoints) for k, v in checkpoint['model'].items()}
        else:
            if checkpoint['config'] != average['config']:
                raise ValueError('模型配置不一致')
            for key, value in checkpoint['model'].items():
                average['model'][key].add_(value, alpha=1/len(checkpoints))
    sources = [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in checkpoints]
    average['averaged_sources'] = sources
    torch.save(average, output/'average.pt')
    model, _ = load_model(output/'average.pt', device)
    validation = validate_generation(model, read_examples(data/'development.jsonl'), device,
                                     summary['plan']['selection_candidates'])
    original = json.loads((source/f"validation-{summary['best_step']}.json").read_text())
    improved = tuple(validation['score']) > tuple(original['score'])
    average['generation_score'] = validation['score']
    torch.save(average, output/'average.pt')
    selected = output/'average.pt' if improved else source/'best.pt'
    shutil.copyfile(selected, output/'best.pt')
    write_json(output/'validation-average.json', validation)
    write_json(output/'validation-original.json', original)
    run = {'operation': '后四个检查点等权平均；仅开发完整成功率提高时采用',
           'source_run': str(source), 'sources': sources, 'average_selected': improved,
           'selected': str(selected), 'parameters': model.parameter_report(),
           'data_sha256': hashlib.sha256((data/'examples.jsonl').read_bytes()).hexdigest(),
           'development_sha256': hashlib.sha256((data/'development.jsonl').read_bytes()).hexdigest(),
           'code_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('training').rglob('*.py')}}
    write_json(output/'run.json', run)
    write_json(output/'training-summary.json', {**run, 'completed_steps': 0,
        'seconds': time.monotonic()-started, 'note': '本操作不执行梯度训练，不增加参数或候选预算。'})
    print(json.dumps({'采用均值模型': improved, '原分数': original['score'],
                      '均值分数': validation['score']}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
