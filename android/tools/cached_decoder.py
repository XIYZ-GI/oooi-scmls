"""可导出到 PyTorch Lite 的增量解码器；复用服务器的键值缓存计算口径。"""

from typing import List

import torch
from torch import nn
from torch.nn import functional as F


class CachedLayer(nn.Module):
    """单层解码：固定的编码器键值只投影一次，历史键值按位置写入。"""

    def __init__(self, layer, heads: int):
        super().__init__()
        self.layer = layer
        self.heads = heads

    def heads_for(self, value: torch.Tensor) -> torch.Tensor:
        return value.reshape(value.shape[0], value.shape[1], self.heads, -1).transpose(1, 2)

    def memory_for(self, memory: torch.Tensor):
        width = memory.shape[-1]
        attention = self.layer.multihead_attn
        key, value = F.linear(memory, attention.in_proj_weight[width:],
                              attention.in_proj_bias[width:]).chunk(2, dim=-1)
        return self.heads_for(key), self.heads_for(value)

    def forward(self, value: torch.Tensor, keys: torch.Tensor, values: torch.Tensor,
                memory_key: torch.Tensor, memory_value: torch.Tensor,
                self_mask: torch.Tensor, cross_mask: torch.Tensor, index: int):
        attention = self.layer.self_attn
        query, key, state = F.linear(self.layer.norm1(value), attention.in_proj_weight,
                                     attention.in_proj_bias).chunk(3, dim=-1)
        keys[:, :, index:index + 1] = self.heads_for(key)
        values[:, :, index:index + 1] = self.heads_for(state)
        attended = F.scaled_dot_product_attention(
            self.heads_for(query), keys[:, :, :index + 1], values[:, :, :index + 1],
            attn_mask=self_mask,
        ).transpose(1, 2).flatten(2)
        value = value + attention.out_proj(attended)
        attention = self.layer.multihead_attn
        width = value.shape[-1]
        query = F.linear(self.layer.norm2(value), attention.in_proj_weight[:width],
                         attention.in_proj_bias[:width])
        attended = F.scaled_dot_product_attention(
            self.heads_for(query), memory_key, memory_value, attn_mask=cross_mask,
        ).transpose(1, 2).flatten(2)
        value = value + attention.out_proj(attended)
        return value + self.layer.linear2(self.layer.activation(self.layer.linear1(self.layer.norm3(value))))


class CachedDecoder(nn.Module):
    """每个位置仅计算一次；缓存仅属于当前调用，不跨任务共享。"""

    def __init__(self, model):
        super().__init__()
        self.heads = model.heads
        self.tokens = model.tokens
        self.layers = nn.ModuleList([CachedLayer(layer, model.heads) for layer in model.decoder.layers])
        self.norm = model.decoder.norm
        self.block_head = model.block_head
        self.relative = model.decoder_relative
        self.cross_relative = model.decoder_cross_relative

    def forward(self, condition: torch.Tensor, memory: torch.Tensor, coords: torch.Tensor,
                padding: torch.Tensor, temperature: float):
        batch, length, width = memory.shape
        keys = torch.jit.annotate(List[torch.Tensor], [])
        values = torch.jit.annotate(List[torch.Tensor], [])
        memory_keys = torch.jit.annotate(List[torch.Tensor], [])
        memory_values = torch.jit.annotate(List[torch.Tensor], [])
        for prepared_layer in self.layers:
            key, value = prepared_layer.memory_for(memory)
            memory_keys.append(key)
            memory_values.append(value)
            keys.append(memory.new_empty((batch, self.heads, length, width // self.heads)))
            values.append(memory.new_empty((batch, self.heads, length, width // self.heads)))

        mask = ~padding[:, None, None, :]
        self_bias = memory.new_zeros((batch, 1, 1, length)).masked_fill(~mask, float('-inf'))
        cross_bias = self_bias
        if self.relative is not None and self.cross_relative is not None:
            self_bias = self.relative(coords, coords).masked_fill(~mask, float('-inf'))
            cross_bias = self.cross_relative(coords, coords).masked_fill(~mask, float('-inf'))

        token = torch.full((batch,), 25, dtype=torch.long, device=memory.device)
        generated = torch.jit.annotate(List[torch.Tensor], [])
        hidden = torch.jit.annotate(List[torch.Tensor], [])
        for index in range(length):
            value = self.tokens(token[:, None]) + condition[:, index:index + 1]
            self_row = self_bias[:, :, :1, :index + 1]
            cross_row = cross_bias[:, :, :1]
            if self.relative is not None:
                self_row = self_bias[:, :, index:index + 1, :index + 1]
                cross_row = cross_bias[:, :, index:index + 1]
            for layer_index, layer in enumerate(self.layers):
                value = layer(value, keys[layer_index], values[layer_index],
                              memory_keys[layer_index], memory_values[layer_index],
                              self_row, cross_row, index)
            state = self.norm(value)
            logits = self.block_head(state[:, 0]).float()
            if temperature > 0:
                token = torch.multinomial((logits / temperature).softmax(-1), 1).squeeze(-1)
            else:
                token = logits.argmax(-1)
            token = token.masked_fill(padding[:, index], 0)
            generated.append(token)
            hidden.append(state)
        return torch.stack(generated, dim=1), torch.cat(hidden, dim=1)
