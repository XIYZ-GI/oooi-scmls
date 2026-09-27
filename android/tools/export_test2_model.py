"""导出 oooi-scmls-v1.1-preview 的安卓 Lite 权重。"""

import hashlib
import json
import sys
from pathlib import Path

import torch
from torch import nn
from torch.nn import functional as F

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from training.constants import BOS, STATES
from training.model import Generator


class ExactAndroidGenerator(nn.Module):
    """精确位置编码模型的显式张量 Lite 前向。"""

    def __init__(self, model: Generator):
        super().__init__()
        self.condition = model.condition
        self.tokens = model.tokens
        self.relations = model.relations
        self.encoder = model.encoder
        self.memory_norm = model.memory_norm
        self.decoder = model.decoder
        self.output_norm = model.output_norm
        self.block_head = model.block_head
        self.push_head = model.push_head
        self.heads = model.heads

    def _encode(self, features, coords, padding):
        batch = {"features": features, "coords": coords, "padding": padding.to(torch.bool)}
        relation = self.relations(coords, batch["padding"])
        value = self.condition(features)
        for layer in self.encoder:
            value = layer(value, value, relation, batch["padding"])
        return self.memory_norm(value), relation

    def _decode(self, tokens, features, padding, memory, relation):
        batch = {"features": features, "padding": padding.to(torch.bool)}
        embedded = self.tokens(tokens) + self.condition(features[:, :tokens.shape[1]])
        self_relation = relation[:, :, :, :tokens.shape[1], :tokens.shape[1]]
        cross_relation = relation[:, :, :, :tokens.shape[1]]
        value = embedded
        for layer in self.decoder:
            value = layer(value, memory, self_relation, batch["padding"][:, :tokens.shape[1]],
                          cross_relation, batch["padding"])
        value = self.output_norm(value)
        return self.block_head(value), value

    def _heads(self, value):
        return value.reshape(value.shape[0], value.shape[1], self.heads, -1).transpose(1, 2)

    @torch.jit.export
    def generate(self, features, coords, padding, temperature: float):
        padding = padding.to(torch.bool)
        memory, relation = self._encode(features, coords, padding)
        size, length = features.shape[0], features.shape[1]
        condition = self.condition(features)
        memory_keys = torch.jit.annotate(list[torch.Tensor], [])
        memory_values = torch.jit.annotate(list[torch.Tensor], [])
        keys = torch.jit.annotate(list[torch.Tensor], [])
        values = torch.jit.annotate(list[torch.Tensor], [])
        gates = torch.jit.annotate(list[torch.Tensor], [])
        head_width = memory.shape[-1] // self.heads
        for decoder_layer in self.decoder:
            normed_memory = decoder_layer.memory_norm(memory)
            attention = decoder_layer.cross_attention
            memory_keys.append(self._heads(attention.key(normed_memory)))
            memory_values.append(self._heads(attention.value(normed_memory)))
            keys.append(memory.new_empty((size, self.heads, length, head_width)))
            values.append(memory.new_empty((size, self.heads, length, head_width)))
            gates.append(memory.new_empty((size, self.heads, length)))
        token = torch.full((size, 1), 25, dtype=torch.long, device=features.device)
        generated = torch.jit.annotate(list[torch.Tensor], [])
        hidden = torch.jit.annotate(list[torch.Tensor], [])
        for index in range(length):
            value = self.tokens(token) + condition[:, index:index + 1]
            self_relation = relation[:, :, :, index:index + 1, :index + 1]
            cross_relation = relation[:, :, :, index:index + 1]
            self_padding = padding[:, :index + 1]
            question = padding[:, index:index + 1]
            for layer_index, layer in enumerate(self.decoder):
                self_attention = layer.self_attention
                normed = layer.norm1(value)
                query = self_attention.query(normed)
                keys[layer_index][:, :, index:index + 1] = self._heads(self_attention.key(normed))
                values[layer_index][:, :, index:index + 1] = self._heads(self_attention.value(normed))
                qgate, kgate = self_attention.gates(normed, normed)
                gates[layer_index][:, :, index:index + 1] = kgate[:, :, 0]
                bias = self_attention.bias_from_gates(qgate, gates[layer_index][:, :, None, :index + 1],
                                                 self_relation, self_padding, dtype=query.dtype)
                attended = F.scaled_dot_product_attention(self._heads(query),
                    keys[layer_index][:, :, :index + 1], values[layer_index][:, :, :index + 1],
                    attn_mask=bias)
                value = value + self_attention.output(attended.transpose(1, 2).flatten(2))
                cross_attention = layer.cross_attention
                normed = layer.norm2(value)
                query = cross_attention.query(normed)
                bias = cross_attention.bias(normed, layer.memory_norm(memory), cross_relation, padding,
                                      dtype=query.dtype)
                attended = F.scaled_dot_product_attention(self._heads(query), memory_keys[layer_index],
                    memory_values[layer_index], attn_mask=bias)
                value = value + cross_attention.output(attended.transpose(1, 2).flatten(2))
                value = value + layer.ffn(layer.norm3(value))
                value = value.masked_fill(question[..., None], 0.0)
            state = self.output_norm(value)
            current = self.block_head(state[:, 0]).float()
            next_token = current.argmax(-1)
            if temperature > 0:
                next_token = torch.multinomial((current / temperature).softmax(-1), 1)[:, 0]
            next_token = next_token.masked_fill(padding[:, index], 0)
            generated.append(next_token)
            hidden.append(state)
            token = next_token[:, None]
        tokens = torch.stack(generated, dim=1)
        states = torch.cat(hidden, dim=1)
        scores = self.push_head(states + self.tokens(tokens.clamp(min=0))).squeeze(-1)
        occupied = (tokens > 0) & (tokens < 25) & ~padding.to(torch.bool)
        same_column = (coords[:, :, None, :2] == coords[:, None, :, :2]).all(-1)
        behind = coords[:, None, :, 2] < coords[:, :, None, 2]
        accessible = occupied & ~(same_column & behind & occupied[:, None, :]).any(-1)
        scores = scores.masked_fill(~accessible, -1e4)
        scores = scores.masked_fill(padding.to(torch.bool), -1e9)
        return tokens, scores.argmax(-1)

    def forward(self, features, coords, padding):
        return self.generate(features, coords, padding, 0.0)


def main():
    checkpoint = ROOT / "data/generation/oooi-scmls-v1.1-preview/run/final.pt"
    output = ROOT / "android/app/src/main/assets"
    checkpoint_data = torch.load(checkpoint, map_location="cpu", weights_only=True)
    model = Generator(**checkpoint_data["config"]).eval()
    model.load_state_dict(checkpoint_data["model"])
    exported = ExactAndroidGenerator(model).eval()
    scripted = torch.jit.script(exported)
    path = output / "oooi-scmls-v1.1-preview.pt"
    scripted._save_for_lite_interpreter(str(path))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    metadata = {
    "id": "oooi-scmls-v1.1-preview", "name": "oooi-scmls-v1.1-preview",
        "architecture": "autoregressive_v1", "inference": "exact_full_prefix_v1",
        "config": checkpoint_data["config"], "parameters": 10887548,
        "feature_columns": 12, "states": [[kind, facing] for kind, facing in STATES],
        "bos": BOS, "checkpoint_step": int(checkpoint_data.get("step", 0)),
        "torch_sha256": digest,
    }
    (output / "oooi-scmls-v1.1-preview.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
    print(path, digest)


if __name__ == "__main__":
    main()
