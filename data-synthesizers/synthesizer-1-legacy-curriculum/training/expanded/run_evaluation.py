"""训练结束后冻结模型，顺序执行旧模型和新模型的配对评估。"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

from ..serialization import write_json


def main():
    parser = argparse.ArgumentParser(description='第四阶段冻结模型与统一预算评估')
    parser.add_argument('--runs', default='runs/stage4')
    parser.add_argument('--data', default='data/generation/stage4')
    args = parser.parse_args()
    runs, data = Path(args.runs), Path(args.data)
    deadline = time.monotonic()+7500
    while not (runs/'training-summary.json').exists():
        if time.monotonic() > deadline:
            raise RuntimeError('训练尚未完成，停止等待，不评估未冻结检查点')
        time.sleep(10)
    frozen = runs/'frozen.pt'
    if not frozen.exists():
        shutil.copyfile(runs/'best.pt', frozen)
    previous = 'runs/stage3-balanced/best.pt'
    write_json(runs/'frozen-checkpoints.json', {name: hashlib.sha256(Path(path).read_bytes()).hexdigest()
                                             for name, path in [('current', frozen), ('previous', previous)]})
    for name, checkpoint in [('current', str(frozen)), ('previous', previous)]:
        datasets = ['heldout', 'retention', 'thickness']
        if (data/'fresh.jsonl').exists():
            datasets.append('fresh')
        for split in datasets:
            output = runs/(name+'-'+split)
            if (output/'report.json').exists():
                continue
            with (runs/(name+'-'+split+'.log')).open('w') as log:
                subprocess.run([sys.executable, '-u', '-m', 'training.expanded.evaluate', '--checkpoint', checkpoint,
                                '--data', str(data/(split+'.jsonl')), '--output', str(output)],
                               stdout=log, stderr=subprocess.STDOUT, check=True)
    subprocess.run([sys.executable, '-m', 'training.expanded.finish', '--runs', str(runs), '--data', str(data)], check=True)


if __name__ == '__main__':
    main()
