"""精确相对位置模型的增量解码：逐步只算当前查询那一行，分数与整段前向一致。

整段前向每层都要用查询与键的内容门控合成位置偏置，因此缓存解码时不能把
偏置整张算好，只能按行取关系分数再补上当前查询的门控；键侧的门控与投影
在一次前向里固定，建成缓存后逐步复用。
"""

import torch
from torch.nn import functional as F

from ..constants import BOS
from ..data import batch_tasks
from ..serialization import decode_structure, digest, positions


def heads(value, count):
    return value.unflatten(-1, (count, value.shape[-1]//count)).transpose(1, 2)


def attend(attention, query, key, value, bias):
    result = F.scaled_dot_product_attention(query, key, value, attn_mask=bias)
    return attention.output(result.transpose(1, 2).flatten(2))


class ExactDecoderCache:
    """``ExactRelations`` 模型的缓存解码器；只在推理期使用。"""

    def __init__(self, model, batch):
        if model.training:
            raise ValueError('增量缓存只用于推理')
        self.model, self.batch = model, batch
        self.condition = model.condition(batch['features'])
        self.relation = model.relation_scores(batch)
        memory = model.encode(batch, self.relation)
        self.memory, self.keys, self.values, self.history = [], [], [], []
        self.gates = []
        size, length, width = memory.shape
        for layer in model.decoder:
            normed = layer.memory_norm(memory)
            self.memory.append(normed)
            self.keys.append(heads(layer.cross_attention.key(normed), model.heads))
            self.values.append(heads(layer.cross_attention.value(normed), model.heads))
            shape = (size, model.heads, length, width//model.heads)
            self.history.append((memory.new_empty(shape), memory.new_empty(shape)))
            # 自注意力的键侧门控只与键自身内容有关，按位置缓存一次即可。
            self.gates.append(memory.new_empty((size, model.heads, length)))

    def step(self, token, index):
        model = self.model
        value = model.tokens(token[:, None]) + self.condition[:, index:index+1]
        self_padding = self.batch['padding'][:, :index+1]
        self_relation = self.relation[:, :, :, index:index+1, :index+1]
        cross_relation = self.relation[:, :, :, index:index+1]
        question = self.batch['padding'][:, index:index+1]
        for i, layer in enumerate(model.decoder):
            attention = layer.self_attention
            normed = layer.norm1(value)
            query = attention.query(normed)
            keys, values = self.history[i]
            keys[:, :, index:index+1] = heads(attention.key(normed), model.heads)
            values[:, :, index:index+1] = heads(attention.value(normed), model.heads)
            qgate, kgate = attention.gates(normed, normed)
            self.gates[i][:, :, index:index+1] = kgate[:, :, 0]
            # 关系对只取到当前位为止的键，因果屏蔽已经由切片自身保证。
            bias = attention.bias_from_gates(qgate, self.gates[i][:, :, None, :index+1], self_relation,
                                             self_padding, dtype=query.dtype)
            value = value + attend(attention, heads(query, model.heads), keys[:, :, :index+1],
                                   values[:, :, :index+1], bias.to(query.dtype))
            attention = layer.cross_attention
            normed = layer.norm2(value)
            query = attention.query(normed)
            bias = attention.bias(normed, self.memory[i], cross_relation, self.batch['padding'],
                                  dtype=query.dtype)
            value = value + attend(attention, heads(query, model.heads), self.keys[i], self.values[i],
                                   bias.to(query.dtype))
            value = value + layer.dropout(layer.ffn(layer.norm3(value)))
            value = value.masked_fill(question[..., None], 0.0)
        hidden = model.output_norm(value)
        return model.block_head(hidden[:, 0]), hidden


@torch.inference_mode()
def generate(model, tasks, device, temperature=0.0, on_progress=None):
    batch = batch_tasks(tasks, device, **model.feature_options)
    cache = ExactDecoderCache(model, batch)
    token = torch.full((len(tasks),), BOS, device=device, dtype=torch.long)
    tokens, hidden = [], []
    for index in range(batch['padding'].shape[1]):
        logits, state = cache.step(token, index)
        logits = logits.float()
        token = logits.argmax(-1) if temperature == 0 else torch.multinomial((logits/temperature).softmax(-1), 1)[:, 0]
        token = token.masked_fill(batch['padding'][:, index], 0)
        tokens.append(token)
        hidden.append(state)
        if on_progress and ((index+1) % 8 == 0 or index+1 == batch['padding'].shape[1]):
            on_progress(index+1, batch['padding'].shape[1])
    tokens = torch.stack(tokens, dim=1)
    push = model.push_logits(torch.cat(hidden, dim=1), tokens, batch).argmax(-1)
    return [decode_structure(task, tokens[i, :len(positions(task))].tolist(), int(push[i]))
            for i, task in enumerate(tasks)]


@torch.inference_mode()
def generate_group(model, records, device, candidates, seed):
    tasks = [r['task'] for r in records for _ in range(candidates)]
    batch = batch_tasks(tasks, device, **model.feature_options)
    cache = ExactDecoderCache(model, batch)
    token = torch.full((len(tasks),), BOS, device=device, dtype=torch.long)
    # 每个需求保留独立随机流，组批方式改变也不改变随机数来源。
    generators = [torch.Generator(device=device).manual_seed(int(digest(['cached_generation', seed, r['task_id']])[:8], 16))
                  for r in records]
    tokens, hidden = [], []
    for index in range(batch['padding'].shape[1]):
        logits, state = cache.step(token, index)
        values = logits.float().reshape(len(records), candidates, -1)
        chosen = []
        for i, generator in enumerate(generators):
            greedy = values[i, :1].argmax(-1)
            sampled = torch.multinomial((values[i, 1:]/.7).softmax(-1), 1, generator=generator)[:, 0] if candidates > 1 else greedy[:0]
            chosen.append(torch.cat([greedy, sampled]))
        token = torch.cat(chosen).masked_fill(batch['padding'][:, index], 0)
        tokens.append(token)
        hidden.append(state)
    tokens = torch.stack(tokens, dim=1)
    push = model.push_logits(torch.cat(hidden, dim=1), tokens, batch).argmax(-1)
    tokens, push = tokens.cpu().tolist(), push.cpu().tolist()
    proposals = [decode_structure(task, tokens[i][:len(positions(task))], push[i]) for i, task in enumerate(tasks)]
    return [proposals[i*candidates:(i+1)*candidates] for i in range(len(records))]
