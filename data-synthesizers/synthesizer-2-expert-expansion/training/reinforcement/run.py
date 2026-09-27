"""完成训练、冻结模型、同预算验收并据实判断阶段是否达标。"""

from concurrent.futures import ProcessPoolExecutor
import argparse
import json
import multiprocessing
from pathlib import Path
import shutil
import subprocess
import sys

import torch

from ..data import read_examples
from ..inference import load_model
from ..serialization import write_json
from .assess import assess, file_sha


def main():
    parser = argparse.ArgumentParser(description='第五阶段训练和最终验收编排')
    parser.add_argument('--data', default='data/generation/stage5')
    parser.add_argument('--output', default='runs/stage5')
    parser.add_argument('--plan')
    args = parser.parse_args()
    root, output = Path(args.data), Path(args.output)
    plan = json.loads(Path(args.plan or root/'experiment-plan.json').read_text())
    if not (output/'training-summary.json').exists():
        subprocess.run([sys.executable, '-u', '-m', 'training.reinforcement.train',
                        '--data', str(root), '--output', str(output),
                        *(['--plan', args.plan] if args.plan else [])], check=True)
    if not (output/'frozen.pt').exists():
        # 对照必须包含实际更新后的策略；初始模型另列为baseline，不伪称PPO产物。
        choices = []
        for path in output.glob('development-*/report.json'):
            iteration = int(path.parent.name.split('-')[-1])
            if iteration > 0 and (output/f'checkpoint-{iteration}.pt').exists():
                choices.append((json.loads(path.read_text())['successes'], iteration))
        score, iteration = max(choices)
        shutil.copyfile(output/f'checkpoint-{iteration}.pt', output/'frozen.pt')
        write_json(output/'selection.json', {'iteration': iteration, 'development_successes': score,
            'rule': '仅从已更新策略中按开发集完整通过数选取，同分取较晚检查点；初始权重单列对照。'})
    torch.set_num_threads(1)
    torch.backends.cuda.matmul.allow_tf32 = True
    reports = {}
    with ProcessPoolExecutor(max_workers=plan['workers'], mp_context=multiprocessing.get_context('spawn')) as pool:
        for name, path in [('baseline', root/'initial.pt'), ('ppo', output/'frozen.pt')]:
            model, _ = load_model(path, 'cuda')
            reports[name] = {}
            for split in ('heldout', 'web-regression', 'expert-regression'):
                target = output/(name+'-'+split)
                if (target/'report.json').exists():
                    report = json.loads((target/'report.json').read_text())
                else:
                    report = assess(model, read_examples(root/(split+'.jsonl')), pool, target)
                    report['checkpoint_sha256'] = file_sha(path)
                    write_json(target/'report.json', report)
                reports[name][split] = report
                print(json.dumps({'模型': name, '集合': split, '报告': report}, ensure_ascii=False), flush=True)
            del model
    before, after = reports['baseline'], reports['ppo']
    gates = plan['success_gate']
    checks = {
        'heldout_gain': after['heldout']['successes']-before['heldout']['successes'] >= gates['heldout_gain'],
        'heldout_multigroup_gain': after['heldout']['families']['multigroup']['successes']-before['heldout']['families']['multigroup']['successes'] >= gates['heldout_multigroup_gain'],
        'web_gain': after['web-regression']['successes']-before['web-regression']['successes'] >= gates['web_gain'],
        'expert_retention': after['expert-regression']['successes'] >= before['expert-regression']['successes']-gates['expert_max_regression'],
    }
    write_json(output/'stage-result.json', {'stage': 5, 'algorithm': 'PPO', 'training_executed': True,
        'accepted': all(checks.values()), 'checks': checks, 'reports': reports,
        'checkpoint_sha256': file_sha(output/'frozen.pt'),
        'note': '训练执行完成与阶段达标分别记录；未达门槛时不替换网页正式模型。'})
    print((output/'stage-result.json').read_text(), flush=True)


if __name__ == '__main__':
    main()
