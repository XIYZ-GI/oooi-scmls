"""保存最终同预算对照任务，严格保留第三阶段原需求条件。"""

import json
from pathlib import Path

from ..compact_round2.prepare import write_rows
from ..serialization import digest, write_json


def main():
    root = Path('data/generation/stage4')
    runs = root.parent/'stage3-complete/artifacts/runs/stage3-balanced'
    previous = []
    for split in ('heldout', 'regression', 'thickness'):
        records = [json.loads(line) for line in (runs/f'current-{split}/results.jsonl').read_text().splitlines()]
        rows = [{k: r[k] for k in ('task_id', 'task', 'family', 'group')} for r in records]
        for row in rows:
            row['split'] = 'test'
        if split == 'thickness':
            write_rows(root/'thickness.jsonl', rows)
        else:
            previous.extend(rows)
    write_rows(root/'retention.jsonl', previous)
    write_json(root/'evaluation-plan.json', {'candidate_budget': 8, 'seeds': [41],
        'datasets': {name: digest((root/(name+'.jsonl')).read_text()) for name in ('heldout', 'retention', 'thickness')},
        'checkpoint_selection': '仅开发集合完整生成选模，冻结后评估保留集合；历史任务单列。',
        'scope': '路径骨架隔离、密集输出组合、旧能力与厚度分别评价；不汇总声称全是新来源。'})


if __name__ == '__main__':
    main()
