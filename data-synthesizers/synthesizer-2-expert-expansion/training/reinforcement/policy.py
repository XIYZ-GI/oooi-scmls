"""生成器共享表示上的状态价值头；推理只需要原生成器权重。"""

import torch
from torch import nn


class ActorCritic(nn.Module):
    def __init__(self, actor):
        super().__init__()
        self.actor = actor
        width = actor.config['width']
        self.value = nn.Sequential(nn.Linear(width, width), nn.Tanh(), nn.Linear(width, 1))
        nn.init.zeros_(self.value[-1].weight)
        nn.init.zeros_(self.value[-1].bias)

    def push_value(self, hidden, tokens, padding):
        state = hidden+self.actor.tokens(tokens.clamp(min=0))
        state = state.masked_fill(padding[:, :, None], 0).sum(1)/(~padding).sum(1, keepdim=True)
        return self.value(state.detach()).squeeze(-1)

    def forward(self, batch, temperature):
        logits, hidden = self.actor.decode(batch['inputs'], batch, self.actor.encode(batch))
        push_logits = self.actor.push_logits(hidden, batch['labels'], batch)
        token_logp = (logits.float()/temperature).log_softmax(-1)
        push_logp = (push_logits.float()/temperature).log_softmax(-1)
        chosen = token_logp.gather(-1, batch['labels'].clamp(min=0)[:, :, None]).squeeze(-1)
        push = push_logp.gather(-1, batch['pushes'][:, None]).squeeze(-1)
        entropy = -(token_logp.exp()*token_logp).sum(-1)
        push_entropy = -(push_logp.exp()*push_logp).sum(-1)
        # 价值回归只训练价值头；生成器只接收策略、熵及KL梯度。
        values = self.value(hidden.detach()).squeeze(-1)
        push_values = self.push_value(hidden, batch['labels'], batch['padding'])
        return chosen, push, values, push_values, entropy, push_entropy, token_logp, push_logp
