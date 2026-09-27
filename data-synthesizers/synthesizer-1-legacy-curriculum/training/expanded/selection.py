"""第四阶段按完整功能选模，各课程单独计分。"""

from collections import defaultdict
import torch

from ..evaluator import evaluate
from ..inference import generate
from ..serialization import digest


def validate_generation(model, records, device, candidates=4):
    model.eval()
    groups = defaultdict(lambda: {'tasks': 0, 'functional': 0})
    details = []
    devices = [torch.cuda.current_device()] if device == 'cuda' else []
    with torch.random.fork_rng(devices=devices):
        for record in records:
            # 每任务固定随机流，任务排序变化不会改变采样条件。
            torch.manual_seed(int(digest(['stage4_development', record['task_id']])[:8], 16))
            task, family = record['task'], record['family']
            group = groups[family]
            group['tasks'] += 1
            proposals = generate(model, [task], device)
            if candidates > 1:
                proposals += generate(model, [task]*(candidates-1), device, 0.7)
            success, seen, reasons = False, set(), []
            for proposal in proposals:
                key = digest(proposal)
                if key in seen:
                    continue
                seen.add(key)
                result = evaluate(task, proposal)
                reasons.append(result['reason'])
                if result['accepted']:
                    success = True
                    break
            group['functional'] += success
            details.append({'task_id': record['task_id'], 'family': family, 'accepted': success, 'reasons': reasons})
    rates = [r['functional']/r['tasks'] for r in groups.values()]
    return {'families': dict(groups), 'score': [min(rates), sum(rates)/len(rates)], 'details': details}
