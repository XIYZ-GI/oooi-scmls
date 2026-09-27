"""冻结同一模型后比较新组合与历史回归需求，不将二者混为独立泛化。"""

import hashlib
import json
from pathlib import Path
import subprocess
import sys

from ..data import read_examples
from ..serialization import digest, write_json
from .config import DATA, RUNS
from .prepare import write_rows


def main():
    summary = json.loads((RUNS/'training-summary.json').read_text())
    if summary['data_digest'] != digest((DATA/'examples.jsonl').read_text()):
        raise ValueError('训练数据指纹不一致')
    if summary['heldout_digest'] != digest((DATA/'heldout.jsonl').read_text()):
        raise ValueError('训练后保留需求被修改')
    regression = read_examples('data/generation/stage3/heldout.jsonl')
    regression += read_examples('data/generation/stage3/five-target-heldout.jsonl')
    write_rows(DATA/'regression.jsonl', regression)
    checkpoints = {'previous_best': 'runs/stage3/best.pt', 'previous_last': 'runs/stage3/last.pt',
                   'current': str(RUNS/'best.pt')}
    frozen = {arm: hashlib.sha256(Path(p).read_bytes()).hexdigest() for arm, p in checkpoints.items()}
    target = RUNS/'frozen-checkpoints.json'
    if target.exists() and json.loads(target.read_text()) != frozen:
        raise ValueError('评估检查点发生变化')
    write_json(target, frozen)
    reports = {}
    for arm, checkpoint in checkpoints.items():
        for subset in ('heldout', 'regression'):
            output = RUNS/(arm+'-'+subset)
            if not (output/'report.json').exists():
                with (RUNS/(arm+'-'+subset+'.log')).open('w') as log:
                    subprocess.run([sys.executable, '-m', 'training.benchmark', '--data', str(DATA/(subset+'.jsonl')),
                        '--checkpoint', checkpoint, '--output', str(output), '--limit', '100', '--candidates', '8',
                        '--split', 'test', '--seed', '20260926'], stdout=log, stderr=subprocess.STDOUT, check=True)
            report = json.loads((output/'report.json').read_text())
            if report['checkpoint_sha256'] != frozen[arm]:
                raise ValueError('已有评估对应其他检查点')
            report['scope'] = ('未参与训练的目标几何组合；混材机构来自训练专家，不是跨设计来源泛化'
                               if subset == 'heldout' else '历史已查看的强充能、专家与旧课程回归需求，不是全新评估')
            write_json(output/'report.json', report)
            reports[arm+'-'+subset] = report
            print(json.dumps({'arm': arm, 'subset': subset, 'families': report['families']}, ensure_ascii=False), flush=True)
    write_json(RUNS/'result.json', {'reports': reports, 'stage3_complete': False,
        'note': '记录功能评估，阶段完成还需机制证据、覆盖与厚度对照判断，不能仅因训练执行完毕标记完成。'})


if __name__ == '__main__':
    main()
