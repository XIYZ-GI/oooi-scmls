"""四套百题评估集与综合集的正式名称。

依据用户 2026-09-25 的命名：历史188（含其百题）叫「基础航械题」、历史200（含其百题）
叫「简单航械题」、历史300（含其百题）叫「普通航械题」、今天最新的100道叫
「普通航械题-2」，四套百题合成 400 道时叫「综合航械题」。
"""

# 内部键沿用冻结数据里的文件名，对外展示一律用这里的中文名称。
SET_NAMES = {
    'historical188': '基础航械题',
    'historical200': '简单航械题',
    'previous300': '普通航械题',
    'today100': '普通航械题-2',
}
ORDER = ('historical188', 'historical200', 'previous300', 'today100')
# 完整题集与它抽出的百题同名。
FULL_SET_NAMES = {
    'historical188': '基础航械题',
    'historical200': '简单航械题',
    'historical300': '普通航械题',
}
COMBINED_NAME = '综合航械题'


def name(suite):
    """按内部键取正式名称；未知键原样返回，避免影响历史实验的目录名。"""
    return SET_NAMES.get(suite, suite)
