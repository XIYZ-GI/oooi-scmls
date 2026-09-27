"""按当前策略批量采样完整结构及推动点，保存真实行为概率。"""

import torch

from ..accelerated.decoding import DecoderCache
from ..constants import BOS
from ..data import batch_tasks
from ..serialization import decode_structure, positions


@torch.inference_mode()
def collect(policy, records, temperature, device='cuda'):
    policy.eval()
    tasks = [r['task'] for r in records]
    batch = batch_tasks(tasks, device)
    cache = DecoderCache(policy.actor, batch)
    token = torch.full((len(tasks),), BOS, device=device, dtype=torch.long)
    tokens, states, logps, values = [], [], [], []
    for index in range(batch['padding'].shape[1]):
        logits, hidden = cache.step(token, index)
        distribution = (logits.float()/temperature).log_softmax(-1)
        token = torch.multinomial(distribution.exp(), 1).squeeze(-1)
        logps.append(distribution.gather(-1, token[:, None]).squeeze(-1))
        token = token.masked_fill(batch['padding'][:, index], 0)
        tokens.append(token)
        states.append(hidden)
        values.append(policy.value(hidden[:, 0]).squeeze(-1))
    tokens = torch.stack(tokens, 1)
    hidden = torch.cat(states, 1)
    push_distribution = (policy.actor.push_logits(hidden, tokens, batch).float()/temperature).log_softmax(-1)
    pushes = torch.multinomial(push_distribution.exp(), 1).squeeze(-1)
    push_logps = push_distribution.gather(-1, pushes[:, None]).squeeze(-1).cpu()
    push_values = policy.push_value(hidden, tokens, batch['padding']).cpu()
    logps, values = torch.stack(logps, 1).cpu(), torch.stack(values, 1).cpu()
    tokens, pushes = tokens.cpu(), pushes.cpu()
    rows = []
    for i, record in enumerate(records):
        length = len(positions(record['task']))
        rows.append({**record, 'proposal': decode_structure(record['task'], tokens[i, :length].tolist(), int(pushes[i])),
                     'old_logps': logps[i, :length].clone(), 'old_values': values[i, :length].clone(),
                     'old_push_logp': push_logps[i].clone(), 'old_push_value': push_values[i].clone()})
    return rows
