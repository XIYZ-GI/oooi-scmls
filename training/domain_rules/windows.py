"""排除已有过程窗口中同类禁忌布局，不把失败结构用作生成答案。"""

from ..constants import STATES
from .constants import AXES
from .observer import layout_issues


def window_issues(row):
    for step in range(len(row['tokens'])):
        blocks = []
        for i, token in enumerate(row['tokens'][step]):
            if not row['present'][step][i] or not token:
                continue
            kind, facing = STATES[int(token)]
            blocks.append({'position': dict(zip(AXES, map(int, row['coords'][step][i]))),
                           'block': {'kind': kind, 'facing': facing}})
        # 窗口可能截断节点，不能将缺失节点当空气；这里只排除真实相邻。
        issues = layout_issues(blocks, distances=(1,))
        if issues:
            return issues
    return []
