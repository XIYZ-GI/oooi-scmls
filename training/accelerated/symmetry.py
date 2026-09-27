"""利用截面等距变换生成候选，再还原到用户的原始坐标。"""

from copy import deepcopy

from ..compact.transforms import transform
from .decoding import generate


VARIANTS = [(False, 1, 1), (True, 1, 1), (False, -1, 1), (False, 1, -1),
            (True, -1, 1), (True, 1, -1), (False, -1, -1), (True, -1, -1)]
PROTOCOL = 'eight_view_greedy_v1'


def generate_symmetric(model, records, device, candidates, seed, on_progress=None):
    if not 1 <= candidates <= len(VARIANTS):
        raise ValueError('截面变换最多生成八个候选')
    transformed, variants = [], VARIANTS[:candidates]
    for record in records:
        for swap, sx, sy in variants:
            row = {'task': deepcopy(record['task']),
                   'proposal': {'blocks': [], 'push': dict(x=0, y=0, z=-2)}}
            transformed.append(transform(row, swap, sx, sy))
    proposals = generate(model, [r['task'] for r in transformed], device, on_progress=on_progress)
    restored = []
    for index, (row, proposal) in enumerate(zip(transformed, proposals)):
        swap, sx, sy = variants[index % candidates]
        # 先交换再翻转的逆变换，需要在交换坐标时同步交换两个翻转符号。
        row['proposal'] = proposal
        restored.append(transform(row, swap, sy if swap else sx, sx if swap else sy)['proposal'])
    return [restored[i*candidates:(i+1)*candidates] for i in range(len(records))]
