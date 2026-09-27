"""旧能力保持训练：提升推驱回放比例并使用未查看的新组合验收。"""

from collections import Counter
import json
from pathlib import Path

from ..compact.run import choose
from ..data import read_examples
from ..serialization import digest, write_json
from .coverage import select_strata
from .prepare import write_rows
from .rules import geometry


ROOT = Path('data/generation/stage3-balanced')


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    if (ROOT/'manifest.json').exists():
        raise ValueError('已有冻结数据，禁止覆盖')
    source = Path('data/generation/stage3-coverage')
    rows = read_examples(source/'examples.jsonl')
    used = {geometry(r['task']) for path in ('data/generation/stage3-round2/heldout.jsonl', str(source/'heldout.jsonl')) for r in read_examples(path)}
    # 旧开发任务继续用于能力保持；新的最终集合与所有已查看目标几何分开。
    fresh = select_strata([r for r in rows if r['usage'] == 'new_combination' and r['geometry'] not in used], 4)
    heldout = [{**r, 'source_group': r['group'], 'group': r['geometry'], 'split': 'test'} for r in fresh]
    development = read_examples(source/'development.jsonl')
    old = read_examples('data/generation/stage3/examples.jsonl')
    for family in ('legacy_parallel', 'legacy_relay'):
        selected = choose([r for r in old if r['family'] == family and r['split'] == 'validation'], 8)
        development += [{**r, 'usage': 'development', 'geometry': geometry(r['task'])} for r in selected]
    write_rows(ROOT/'examples.jsonl', rows)
    write_rows(ROOT/'development.jsonl', development)
    write_rows(ROOT/'heldout.jsonl', heldout)
    write_rows(ROOT/'additional-regression.jsonl', read_examples(source/'heldout.jsonl'))
    plan = json.loads((source/'experiment-plan.json').read_text())
    plan.update(seed=20260928, steps=6000, initial_checkpoint='runs/stage3-coverage/best.pt',
                validation_interval=1000, learning_rate=0.00004, depth_slack_max=0,
                family_sampling={'legacy': 0.30, 'strong_compact': 0.20, 'strong_wide': 0.15,
                                 'mixed_three': 0.15, 'mixed_two': 0.10, 'strong_staggered': 0.05,
                                 'pull_compact': 0.04, 'expert_compact': 0.01},
                selection='按包括旧推驱在内的全部开发族完整通过率，先最大化最小值，再比较平均值；同分取较早检查点。')
    write_json(ROOT/'experiment-plan.json', plan)
    goal = json.loads((source/'stage-goals.json').read_text())
    goal['coverage_note'] = '8目标混材和11目标同推的新几何已在上次评估用完，继续作回归；新目标组合成功率仅使用未查看的新集合。'
    write_json(ROOT/'stage-goals.json', goal)
    write_json(ROOT/'manifest.json', {'examples': len(rows), 'data_digest': digest((ROOT/'examples.jsonl').read_text()),
        'development_counts': dict(Counter(r['family'] for r in development)),
        'heldout_counts': dict(Counter(r['family']+'/'+str(len(r['task']['targets'])) for r in heldout)),
        'heldout_geometry': len({r['geometry'] for r in heldout}), 'excluded_previously_evaluated_geometry': len(used),
        'scope': '保留新几何与历史回归分开；专家骨架继续共享训练来源，不是跨原理泛化。'})
    print((ROOT/'manifest.json').read_text(), flush=True)


if __name__ == '__main__':
    main()
