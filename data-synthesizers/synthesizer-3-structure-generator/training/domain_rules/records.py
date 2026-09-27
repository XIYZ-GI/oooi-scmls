"""结构示范读取入口的兜底筛选，不改需求与失败反馈。"""

import warnings

from .observer import proposal_issues


def filter_examples(records, origin=''):
    kept = []
    for row in records:
        proposal = row.get('proposal')
        if proposal is not None and proposal_issues(proposal):
            continue
        kept.append(row)
    removed = len(records)-len(kept)
    if removed:
        warnings.warn(f'{origin}：按航械设计禁忌排除 {removed} 条结构记录，保留 {len(kept)} 条。', stacklevel=2)
    return kept
