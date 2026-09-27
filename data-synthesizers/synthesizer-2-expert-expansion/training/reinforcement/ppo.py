"""终局蒙特卡洛回报的裁剪 PPO；动作概率包含方块与推动点。"""

from collections import defaultdict

import torch

from ..data import collate


def update(policy, reference, optimizer, rows, plan, rng):
    # eval关闭dropout，但保留梯度，使采样与更新的策略分布一致。
    policy.eval()
    device = next(policy.parameters()).device
    advantages = torch.cat([r['reward']-r['old_values'] for r in rows])
    mean, scale = float(advantages.mean()), max(float(advantages.std()), .05)
    normalizers = {}
    if plan.get('normalize_advantage_by_demand'):
        grouped = defaultdict(list)
        for row in rows:
            grouped[row['task_id']].append(row['reward']-row['old_values'])
        for key, values in grouped.items():
            values = torch.cat(values)
            normalizers[key] = (float(values.mean()), max(float(values.std()), .1))
    stats = []
    for epoch in range(plan['ppo_epochs']):
        order = list(range(len(rows)))
        rng.shuffle(order)
        for start in range(0, len(order), plan['minibatch']):
            piece = [rows[i] for i in order[start:start+plan['minibatch']]]
            batch = collate(piece, device)
            mask = ~batch['padding']
            length = mask.shape[1]
            old_logps = torch.stack([torch.nn.functional.pad(r['old_logps'], (0, length-len(r['old_logps']))) for r in piece]).to(device)
            old_values = torch.stack([torch.nn.functional.pad(r['old_values'], (0, length-len(r['old_values']))) for r in piece]).to(device)
            old_push_logps = torch.stack([r['old_push_logp'] for r in piece]).to(device)
            old_push_values = torch.stack([r['old_push_value'] for r in piece]).to(device)
            returns = torch.tensor([r['reward'] for r in piece], device=device)
            centers = torch.tensor([normalizers.get(r['task_id'], (mean, scale))[0] for r in piece], device=device)
            scales = torch.tensor([normalizers.get(r['task_id'], (mean, scale))[1] for r in piece], device=device)
            adv = (returns[:, None]-old_values-centers[:, None])/scales[:, None]
            push_adv = (returns-old_push_values-centers)/scales
            logps, push_logps, values, push_values, entropy, push_entropy, dist, push_dist = policy(batch, plan['temperature'])
            ratio = (logps-old_logps).exp()
            push_ratio = (push_logps-old_push_logps).exp()
            lower, upper = 1-plan['clip_ratio'], 1+plan['clip_ratio']

            def masked_mean(value):
                return ((value*mask).sum(1)/mask.sum(1)).mean()

            actor_loss = -masked_mean(torch.minimum(ratio*adv, ratio.clamp(lower, upper)*adv))
            actor_loss -= torch.minimum(push_ratio*push_adv, push_ratio.clamp(lower, upper)*push_adv).mean()
            value_loss = masked_mean((values-returns[:, None]).square())+(push_values-returns).square().mean()
            with torch.no_grad():
                ref_logits, ref_push = reference(batch)
                ref_dist = (ref_logits.float()/plan['temperature']).log_softmax(-1)
                ref_push = (ref_push.float()/plan['temperature']).log_softmax(-1)
            kl = masked_mean((dist.exp()*(dist-ref_dist)).sum(-1))
            kl += (push_dist.exp()*(push_dist-ref_push)).sum(-1).mean()
            entropy_loss = masked_mean(entropy)+push_entropy.mean()
            loss = actor_loss+plan['value_weight']*value_loss+plan['reference_kl_weight']*kl-plan['entropy_weight']*entropy_loss
            if not torch.isfinite(loss):
                raise RuntimeError('PPO损失出现非有限值，停止更新并保留检查点')
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(policy.parameters(), 1.0)
            optimizer.step()
            with torch.no_grad():
                delta = logps-old_logps
                approx_kl = masked_mean((delta.exp()-1)-delta)
                pushed = push_logps-old_push_logps
                approx_kl += ((pushed.exp()-1)-pushed).mean()
            stats.append({'loss': float(loss.detach()), 'value_loss': float(value_loss.detach()),
                          'reference_kl': float(kl.detach()), 'policy_kl': float(approx_kl),
                          'entropy': float(entropy_loss.detach())})
            if float(approx_kl) > plan['target_kl']*1.5:
                return {key: sum(r[key] for r in stats)/len(stats) for key in stats[0]} | {'updates': len(stats), 'early_stop': True}
    return {key: sum(r[key] for r in stats)/len(stats) for key in stats[0]} | {'updates': len(stats), 'early_stop': False}
