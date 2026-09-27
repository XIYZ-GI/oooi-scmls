"""基于当前方块集合的空间 Transformer，联合选择位置、方块与朝向。"""

from typing import Tuple

import torch
from torch import Tensor, nn
from torch.utils.checkpoint import checkpoint

from ..config import ARCHITECTURE, NON_AIR_STATES
from .relations import ExactRelations
from .layers import SpatialLayer


class SpatialGenerator(nn.Module):
    architecture = ARCHITECTURE

    def __init__(self, width=224, heads=7, encoder_layers=7, decoder_layers=8,
                 relation_width=8, dropout=0.1, max_extent=32, max_volume=1024,
                 max_targets=256, max_blocks=1024, activation_checkpoint=True):
        super().__init__()
        if width % heads or min(width, heads, encoder_layers, decoder_layers, relation_width) < 1:
            raise ValueError('网络宽度、层数与注意力头配置不合法')
        if not 0 <= dropout < 1 or min(max_extent, max_volume, max_targets, max_blocks) < 1:
            raise ValueError('网络范围或丢弃率不合法')
        self.config = dict(width=width, heads=heads, encoder_layers=encoder_layers,
                           decoder_layers=decoder_layers, relation_width=relation_width, dropout=dropout,
                           max_extent=max_extent, max_volume=max_volume, max_targets=max_targets,
                           max_blocks=max_blocks, activation_checkpoint=activation_checkpoint)
        self.max_extent = max_extent
        self.max_volume = max_volume
        self.max_blocks = max_blocks
        self.activation_checkpoint = activation_checkpoint
        # 与关系模块同义：训练期关闭需要主机同步的范围校验，推理与检查保持开启。
        self.strict_checks = True
        self.condition = nn.Sequential(nn.Linear(12, width), nn.GELU(), nn.Linear(width, width))
        # 状态零表示尚未放置；输出词表中没有空气。
        self.states = nn.Embedding(NON_AIR_STATES + 1, width)
        self.relations = ExactRelations(heads, max_extent, relation_width)
        self.encoder = nn.ModuleList([SpatialLayer(width, heads, dropout, False) for _ in range(encoder_layers)])
        self.decoder = nn.ModuleList([SpatialLayer(width, heads, dropout, True) for _ in range(decoder_layers)])
        self.memory_norm = nn.LayerNorm(width)
        self.output_norm = nn.LayerNorm(width)
        self.action_head = nn.Linear(width, NON_AIR_STATES)
        self.stop_head = nn.Sequential(nn.Linear(width + 1, width), nn.GELU(), nn.Linear(width, 1))
        self.push_head = nn.Sequential(nn.Linear(width, width), nn.GELU(), nn.Linear(width, 1))

    @torch.jit.unused
    def checked_layer(self, layer, value, memory, relation, padding):
        return checkpoint(layer, value, memory, relation, padding, use_reentrant=False)

    @torch.jit.export
    def encode(self, features: Tensor, coords: Tensor, padding: Tensor) -> Tuple[Tensor, Tensor]:
        padding = padding.to(torch.bool)
        if features.size(1) > self.max_volume or (self.strict_checks and bool(padding.all(-1).any())):
            raise ValueError('工作区超过体积限制或没有有效格子')
        relation = self.relations(coords, padding)
        value = self.condition(features).masked_fill(padding[..., None], 0.0)
        for layer in self.encoder:
            if not torch.jit.is_scripting() and self.training and self.activation_checkpoint:
                value = self.checked_layer(layer, value, value, relation, padding)
            else:
                value = layer(value, value, relation, padding)
        return self.memory_norm(value), relation

    @torch.jit.export
    def decode(self, memory: Tensor, relation: Tensor, coords: Tensor, padding: Tensor,
               prefix: Tensor) -> Tuple[Tensor, Tensor]:
        padding = padding.to(torch.bool)
        if self.strict_checks and (bool(((prefix < 0) | (prefix > 24)).any())
                                   or bool((padding & (prefix != 0)).any())):
            raise ValueError('当前集合包含非法方块状态或补齐位置')
        value = memory + self.states(prefix)
        for layer in self.decoder:
            if not torch.jit.is_scripting() and self.training and self.activation_checkpoint:
                value = self.checked_layer(layer, value, memory, relation, padding)
            else:
                value = layer(value, memory, relation, padding)
        hidden = self.output_norm(value)
        valid = ~padding
        occupied = (prefix > 0) & valid
        available = valid & ~occupied
        blocks = self.action_head(hidden).masked_fill(~available[..., None], float('-inf'))
        denominator = valid.sum(-1, keepdim=True).clamp_min(1)
        pooled = (hidden * valid[..., None]).sum(1) / denominator
        fraction = occupied.sum(-1, keepdim=True) / denominator
        stop = self.stop_head(torch.cat([pooled, fraction.to(pooled.dtype)], dim=-1))
        stop = stop.masked_fill(~occupied.any(-1, keepdim=True), float('-inf'))
        # 全部位置共同竞争；禁止重复放置，不限制下一位置的编号大小。
        actions = torch.cat([blocks.flatten(1), stop], dim=1)
        same_column = (coords[:, :, None, :2] == coords[:, None, :, :2]).all(-1)
        behind = coords[:, None, :, 2] < coords[:, :, None, 2]
        accessible = occupied & ~(same_column & behind & occupied[:, None, :]).any(-1)
        pushes = self.push_head(hidden).squeeze(-1).masked_fill(~accessible, float('-inf'))
        return actions, pushes

    def forward(self, features: Tensor, coords: Tensor, padding: Tensor,
                prefix: Tensor) -> Tuple[Tensor, Tensor]:
        memory, relation = self.encode(features, coords, padding)
        return self.decode(memory, relation, coords, padding, prefix)

    @torch.jit.unused
    def parameter_report(self):
        return dict(total=sum(p.numel() for p in self.parameters()),
                    components={name: sum(p.numel() for p in module.parameters())
                                for name, module in self.named_children()})
