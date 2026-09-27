"""网页可调候选预算：先生成确定性视角候选，再按模型概率采样。"""

import torch

from ..accelerated.decoding import generate
from ..accelerated.symmetry import VARIANTS, generate_symmetric
from ..compact.transforms import transform
from .config import MAX_CANDIDATES, SAMPLING_TEMPERATURE


def generate_candidates(model, task, count, seed, on_progress):
    if not 1 <= count <= MAX_CANDIDATES:
        raise ValueError(f'候选数量必须在1～{MAX_CANDIDATES}之间')
    volume = task['width']*task['height']*task['depth']
    first_count = min(count, len(VARIANTS))
    proposals = generate_symmetric(
        model, [{'task': task}], 'cpu', first_count, seed,
        on_progress=lambda done, total: on_progress(done*first_count, volume*count),
    )[0]
    # 每批最多八个，限制 CPU 推理缓存；随机种子随结果保存。
    torch.manual_seed(seed)
    while len(proposals) < count:
        offset = len(proposals)
        variants = VARIANTS[:min(len(VARIANTS), count-offset)]
        rows = [transform({'task': task, 'proposal': {'blocks': [], 'push': dict(x=0, y=0, z=-2)}},
                          swap, sx, sy) for swap, sx, sy in variants]
        generated = generate(
            model, [row['task'] for row in rows], 'cpu', temperature=SAMPLING_TEMPERATURE,
            on_progress=lambda done, total: on_progress(offset*volume+done*len(rows), volume*count),
        )
        for row, proposal, (swap, sx, sy) in zip(rows, generated, variants):
            row['proposal'] = proposal
            proposals.append(transform(row, swap, sy if swap else sx, sx if swap else sy)['proposal'])
    return proposals
