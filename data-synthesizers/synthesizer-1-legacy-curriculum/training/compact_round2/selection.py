"""在固定开发需求上按完整功能与实际机制选模。"""

from collections import defaultdict
import torch

from ..compact.mechanisms import analyze
from ..evaluator import evaluate
from ..inference import generate
from ..serialization import digest


def validate_generation(model, records, device, candidates=4):
    model.eval()
    groups = defaultdict(lambda: {'tasks': 0, 'functional': 0, 'mechanism': 0})
    details = []
    devices = [torch.cuda.current_device()] if device == 'cuda' else []
    with torch.random.fork_rng(devices=devices):
        torch.manual_seed(20260926)
        for record in records:
            task, family = record['task'], record['family']
            group = groups[family]
            group['tasks'] += 1
            proposals = generate(model, [task], device)
            if candidates > 1:
                proposals += generate(model, [task]*(candidates-1), device, 0.7)
            functional, mechanism, seen = False, False, set()
            reasons = []
            for proposal in proposals:
                key = digest(proposal)
                if key in seen:
                    continue
                seen.add(key)
                result = evaluate(task, proposal)
                reasons.append(result['reason'])
                if not result['accepted']:
                    continue
                functional = True
                proof = evaluate(task, proposal, True)
                observed = analyze(proof['trace'])
                if family.startswith('legacy_'):
                    valid = True
                elif family.startswith('mixed_'):
                    valid = bool(observed['nonempty_pull_operations'] and observed['mixed_boundaries_separated_in_motion'])
                elif family == 'pull_compact':
                    valid = bool(observed['nonempty_pull_operations'])
                else:
                    valid = bool(observed['strong_power_only_pairs'])
                if valid:
                    mechanism = True
                    break
            group['functional'] += functional
            group['mechanism'] += mechanism
            details.append({'task_id': record['task_id'], 'family': family,
                            'functional': functional, 'mechanism': mechanism, 'reasons': reasons})
    rates = [r['mechanism']/r['tasks'] for r in groups.values()]
    return {'families': dict(groups), 'score': [min(rates), sum(rates)/len(rates)], 'details': details}
