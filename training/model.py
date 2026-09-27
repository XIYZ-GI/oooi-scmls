"""小型空间关系编码器与条件自回归完整结构生成器。"""

import torch
from torch import nn

from .constants import BOS, STATES
from .data import feature_count
from .exact_position import CausalCrossLayer, ExactRelations, SpatialLayer, decoder_relations
from .position import RelativeBias


class RelationLayer(nn.Module):
    def __init__(self, width, heads, dropout):
        super().__init__()
        self.norm1 = nn.LayerNorm(width)
        self.attention = nn.MultiheadAttention(width, heads, dropout=dropout, batch_first=True)
        self.norm2 = nn.LayerNorm(width)
        self.ffn = nn.Sequential(nn.Linear(width, 4*width), nn.GELU(), nn.Dropout(dropout), nn.Linear(4*width, width))
        self.dropout = nn.Dropout(dropout)

    def forward(self, value, bias):
        normed = self.norm1(value)
        value = value + self.dropout(self.attention(normed, normed, normed, attn_mask=bias, need_weights=False)[0])
        return value + self.dropout(self.ffn(self.norm2(value)))


class Generator(nn.Module):
    def __init__(self, width=128, heads=4, encoder_layers=2, decoder_layers=4, dropout=0.1,
                 use_target_z=True, use_run_features=True, decoder_relative=False,
                 exact_relative=False, relation_width=8, relation_extent=32):
        super().__init__()
        self.use_target_z = use_target_z
        self.use_run_features = use_run_features
        self.feature_count = feature_count(use_target_z, use_run_features)
        self.config = dict(width=width, heads=heads, encoder_layers=encoder_layers,
                           decoder_layers=decoder_layers, dropout=dropout, use_target_z=use_target_z,
                           use_run_features=use_run_features, decoder_relative=decoder_relative,
                           exact_relative=exact_relative, relation_width=relation_width,
                           relation_extent=relation_extent)
        self.heads = heads
        # 精确相对位置编码与九档分档编码互斥：前者覆盖全部有符号格距，后者合并档位。
        self.exact_relative = exact_relative
        self.condition = nn.Sequential(nn.Linear(self.feature_count, width), nn.GELU(), nn.Linear(width, width))
        self.memory_norm = nn.LayerNorm(width)
        self.tokens = nn.Embedding(BOS+1, width)
        if exact_relative:
            # 与无序稀疏模型同一份关系模块；解码层额外提供因果自注意力与格子交叉注意力。
            # 分档编码不参与该模式，但保留同名属性便于通用代码按 None 判断。
            self.decoder_relative = None
            self.decoder_cross_relative = None
            self.relations = ExactRelations(heads, relation_extent, relation_width)
            self.encoder = nn.ModuleList([SpatialLayer(width, heads, dropout, False)
                                          for _ in range(encoder_layers)])
            self.decoder = nn.ModuleList([CausalCrossLayer(width, heads, dropout)
                                          for _ in range(decoder_layers)])
            self.output_norm = nn.LayerNorm(width)
        else:
            self.relative = nn.ModuleList([nn.Embedding(17, heads) for _ in range(3)])
            self.adjacency = nn.Embedding(2, heads)
            self.encoder = nn.ModuleList([RelationLayer(width, heads, dropout) for _ in range(encoder_layers)])
            layer = nn.TransformerDecoderLayer(width, heads, 4*width, dropout, activation="gelu",
                                               batch_first=True, norm_first=True)
            self.decoder = nn.TransformerDecoder(layer, decoder_layers, norm=nn.LayerNorm(width))
            # 解码器自注意力与交叉注意力各有一份相对位置偏置；关闭时保持历史结构不变。
            self.decoder_relative = RelativeBias(heads) if decoder_relative else None
            self.decoder_cross_relative = RelativeBias(heads) if decoder_relative else None
        self.block_head = nn.Linear(width, len(STATES))
        self.push_head = nn.Sequential(nn.Linear(width, width), nn.GELU(), nn.Linear(width, 1))

    @property
    def feature_options(self):
        """构造批次时要传给 ``batch_tasks`` 的需求特征口径。"""
        return dict(use_target_z=self.use_target_z, use_run_features=self.use_run_features)

    def relation_scores(self, batch):
        """精确编码下的三轴关系分数；旧分档编码不走这条路径。"""
        return self.relations(batch["coords"], batch["padding"])

    def encode(self, batch, relation=None):
        value = self.condition(batch["features"])
        if self.exact_relative:
            if relation is None:
                relation = self.relation_scores(batch)
            for layer in self.encoder:
                value = layer(value, value, relation, batch["padding"])
            return self.memory_norm(value)
        delta = batch["coords"][:, :, None] - batch["coords"][:, None, :]
        bias = sum(embedding(delta[..., i].clamp(-8, 8)+8) for i, embedding in enumerate(self.relative))
        bias = bias + self.adjacency((delta.abs().sum(-1) == 1).long())
        bias = bias.permute(0, 3, 1, 2).masked_fill(batch["padding"][:, None, None, :], float("-inf"))
        bias = bias.flatten(0, 1)
        for layer in self.encoder:
            value = layer(value, bias)
        return self.memory_norm(value)

    def decode(self, inputs, batch, memory, relation=None):
        length = inputs.shape[1]
        embedded = self.tokens(inputs) + self.condition(batch["features"][:, :length])
        if self.exact_relative:
            if relation is None:
                relation = self.relation_scores(batch)
            self_relation, cross_relation = decoder_relations(relation, length)
            hidden = embedded
            for layer in self.decoder:
                hidden = layer(hidden, memory, self_relation, batch["padding"][:, :length],
                               cross_relation, batch["padding"])
            hidden = self.output_norm(hidden)
            return self.block_head(hidden), hidden
        causal = torch.ones(length, length, dtype=torch.bool, device=inputs.device).triu(1)
        if self.decoder_relative is None:
            hidden = self.decoder(embedded, memory, tgt_mask=causal,
                                  tgt_key_padding_mask=batch["padding"][:, :length],
                                  memory_key_padding_mask=batch["padding"], tgt_is_causal=True)
        else:
            # 相对位置以浮点掩码进入注意力：位置偏置、因果和补齐一次合好，
            # 与手动缓存的推理路径保持同一套分数，避免训练与线上不一致。
            coords = batch["coords"]
            self_bias = self.decoder_relative(coords[:, :length], coords[:, :length])
            self_bias = self_bias.masked_fill(causal[None, None], float('-inf'))
            self_bias = self_bias.masked_fill(batch["padding"][:, None, None, :length], float('-inf'))
            cross_bias = self.decoder_cross_relative(coords[:, :length], coords)
            cross_bias = cross_bias.masked_fill(batch["padding"][:, None, None, :], float('-inf'))
            # 补齐掩码已经合进浮点偏置里，不再单独传布尔补齐掩码，避免两种掩码混用。
            hidden = self.decoder(embedded, memory,
                                  tgt_mask=self_bias.flatten(0, 1).to(embedded.dtype),
                                  memory_mask=cross_bias.flatten(0, 1).to(embedded.dtype),
                                  tgt_is_causal=False, memory_is_causal=False)
        return self.block_head(hidden), hidden

    def push_logits(self, hidden, tokens, batch):
        scores = self.push_head(hidden + self.tokens(tokens.clamp(min=0))).squeeze(-1)
        occupied = (tokens > 0) & (tokens < len(STATES)) & ~batch["padding"]
        coords = batch["coords"]
        same_column = (coords[:, :, None, :2] == coords[:, None, :, :2]).all(-1)
        behind = coords[:, None, :, 2] < coords[:, :, None, 2]
        accessible = occupied & ~(same_column & behind & occupied[:, None, :]).any(-1)
        # 全空气候选保留有限分数，随后由精确评估器明确拒绝。
        scores = scores.masked_fill(~accessible, -1e4)
        # 全空气候选也只能在自身网格内选点，不能采到批次补齐位置。
        return scores.masked_fill(batch['padding'], -1e9)

    def forward(self, batch):
        relation = self.relation_scores(batch) if self.exact_relative else None
        logits, hidden = self.decode(batch["inputs"], batch, self.encode(batch, relation), relation)
        return logits, self.push_logits(hidden, batch["labels"], batch)

    def parameter_report(self):
        groups = {name: sum(p.numel() for p in module.parameters()) for name, module in self.named_children()}
        return {"total": sum(p.numel() for p in self.parameters()), "trainable": sum(p.numel() for p in self.parameters() if p.requires_grad),
                "inference": sum(p.numel() for p in self.parameters()), "components": groups}
