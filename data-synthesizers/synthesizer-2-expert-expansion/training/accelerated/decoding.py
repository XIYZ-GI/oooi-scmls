"""缓存解码层历史键值，生成时不重复计算已经生成的位置。"""

import torch
from torch.nn import functional as F

from ..constants import BOS
from ..data import batch_tasks
from ..serialization import decode_structure, positions, digest


def heads(value, count):
    return value.unflatten(-1, (count, value.shape[-1]//count)).transpose(1, 2)


def attend(module, query, key, value, mask=None):
    result = F.scaled_dot_product_attention(query, key, value, attn_mask=mask)
    result = result.transpose(1, 2).flatten(2)
    return module.out_proj(result)


class DecoderCache:
    def __init__(self, model, batch):
        if model.training:
            raise ValueError('增量缓存只用于推理')
        self.model, self.batch = model, batch
        self.condition = model.condition(batch['features'])
        memory = model.encode(batch)
        self.memory, self.history = [], []
        size, length, width = memory.shape
        for layer in model.decoder.layers:
            attention = layer.multihead_attn
            kv = F.linear(memory, attention.in_proj_weight[width:], attention.in_proj_bias[width:])
            key, value = kv.chunk(2, dim=-1)
            self.memory.append((heads(key, model.heads), heads(value, model.heads)))
            shape = (size, model.heads, length, width//model.heads)
            self.history.append((memory.new_empty(shape), memory.new_empty(shape)))
        self.mask = ~batch['padding'][:, None, None, :]
        # 带相对位置偏置的模型把位置分数一次性算好，逐步解码时按行取用。
        self.self_bias = self.cross_bias = None
        if model.decoder_relative is not None:
            coords = batch['coords']
            length = coords.shape[1]
            causal = torch.ones(length, length, dtype=torch.bool, device=coords.device).triu(1)
            bias = model.decoder_relative(coords, coords).masked_fill(causal[None, None], float('-inf'))
            self.self_bias = bias.masked_fill(batch['padding'][:, None, None, :], float('-inf'))
            cross = model.decoder_cross_relative(coords, coords)
            self.cross_bias = cross.masked_fill(batch['padding'][:, None, None, :], float('-inf'))

    def step(self, token, index):
        model = self.model
        value = model.tokens(token[:, None]) + self.condition[:, index:index+1]
        width = value.shape[-1]
        for i, layer in enumerate(model.decoder.layers):
            module = layer.self_attn
            normed = layer.norm1(value)
            q, k, v = F.linear(normed, module.in_proj_weight, module.in_proj_bias).chunk(3, dim=-1)
            keys, values = self.history[i]
            keys[:, :, index:index+1] = heads(k, model.heads)
            values[:, :, index:index+1] = heads(v, model.heads)
            mask = (self.mask[:, :, :, :index+1] if self.self_bias is None else
                    self.self_bias[:, :, index:index+1, :index+1].to(value.dtype))
            value = value + attend(module, heads(q, model.heads), keys[:, :, :index+1], values[:, :, :index+1],
                                    mask)
            module = layer.multihead_attn
            query = F.linear(layer.norm2(value), module.in_proj_weight[:width], module.in_proj_bias[:width])
            mask = (self.mask if self.cross_bias is None else
                    self.cross_bias[:, :, index:index+1].to(query.dtype))
            value = value + attend(module, heads(query, model.heads), *self.memory[i], mask)
            value = value + layer.linear2(layer.activation(layer.linear1(layer.norm3(value))))
        hidden = model.decoder.norm(value)
        return model.block_head(hidden[:, 0]), hidden


@torch.inference_mode()
def generate(model, tasks, device, temperature=0.0, on_progress=None):
    if getattr(model, 'exact_relative', False):
        from .exact_decoding import generate as generate_exact
        return generate_exact(model, tasks, device, temperature, on_progress)
    batch = batch_tasks(tasks, device, **model.feature_options)
    cache = DecoderCache(model, batch)
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
    return [decode_structure(task, tokens[i, :len(positions(task))].tolist(), int(push[i])) for i, task in enumerate(tasks)]


@torch.inference_mode()
def generate_group(model, records, device, candidates, seed):
    if getattr(model, 'exact_relative', False):
        from .exact_decoding import generate_group as generate_group_exact
        return generate_group_exact(model, records, device, candidates, seed)
    tasks = [r['task'] for r in records for _ in range(candidates)]
    batch = batch_tasks(tasks, device, **model.feature_options)
    cache = DecoderCache(model, batch)
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
        tokens.append(token);hidden.append(state)
    tokens = torch.stack(tokens, dim=1)
    push = model.push_logits(torch.cat(hidden, dim=1), tokens, batch).argmax(-1)
    tokens, push = tokens.cpu().tolist(), push.cpu().tolist()
    proposals = [decode_structure(task, tokens[i][:len(positions(task))], push[i]) for i, task in enumerate(tasks)]
    return [proposals[i*candidates:(i+1)*candidates] for i in range(len(records))]
