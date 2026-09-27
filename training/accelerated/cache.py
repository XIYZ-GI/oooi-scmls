"""将不变的条件与结构编码一次，按索引直接组装设备上的批次。"""

import torch

from ..constants import BOS
from ..data import condition
from ..serialization import encode_structure


class EncodedCache:
    def __init__(self, records, device, use_target_z=True, use_run_features=True):
        features, coords, labels, inputs, starts, lengths, pushes = [], [], [], [], [], [], []
        self.index = {}
        offset = 0
        for row in records:
            if row['id'] in self.index:
                continue
            self.index[row['id']] = len(starts)
            f, c = condition(row['task'], use_target_z, use_run_features)
            tokens, push = encode_structure(row['task'], **row['proposal'])
            features.append(f); coords.append(c)
            labels.append(torch.tensor(tokens))
            inputs.append(torch.tensor([BOS, *tokens[:-1]]))
            starts.append(offset);lengths.append(len(tokens));pushes.append(push)
            offset += len(tokens)
        self.arrays = {name: torch.cat(values).to(device) for name, values in
                       [('features', features), ('coords', coords), ('labels', labels), ('inputs', inputs)]}
        self.starts = torch.tensor(starts, device=device)
        self.lengths = torch.tensor(lengths, device=device)
        self.cpu_lengths = lengths
        self.pushes = torch.tensor(pushes, device=device)
        self.device = device
        self.bytes = sum(t.numel()*t.element_size() for t in self.arrays.values())

    def batch(self, records):
        indices = [self.index[r['id']] for r in records]
        length = max(self.cpu_lengths[i] for i in indices)
        index = torch.tensor(indices, device=self.device)
        offsets = torch.arange(length, device=self.device)[None, :]
        padding = offsets >= self.lengths[index, None]
        positions = self.starts[index, None] + offsets.masked_fill(padding, 0)
        batch = {name: value[positions] for name, value in self.arrays.items()}
        for name in ('features', 'coords'):
            batch[name].masked_fill_(padding[:, :, None], 0)
        batch['labels'].masked_fill_(padding, -100)
        batch['inputs'].masked_fill_(padding, BOS)
        batch.update(padding=padding, pushes=self.pushes[index])
        return batch
