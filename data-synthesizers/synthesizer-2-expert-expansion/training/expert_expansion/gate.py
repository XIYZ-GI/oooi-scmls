"""正式扩量前核对全部专家的需求、引擎版本和完整运行证据。"""

import json

import mcscai_engine

from ..serialization import digest
from .config import ROOT

REQUIRED_NAMES = {f'移动线{i}' for i in (2, 4, 6, *range(7, 22))}


def require_case(expert, row):
    solution = row.get('solution') or {}
    value = solution.get('evaluation') or {}
    if not (row.get('accepted') and value.get('accepted')
            and value.get('foundation', {}).get('accepted')
            and value.get('engine_version') == mcscai_engine.__version__
            and solution.get('assembly_method') == 'constraint_solver_v2'
            and len(value.get('rounds', [])) == 3
            and digest(solution.get('task')) == digest(expert['task'])):
        raise ValueError(expert['name']+'尚未完成当前引擎下同需求三轮构造验收')
    zs = [b['position']['z'] for b in solution['proposal']['blocks']]
    if max(zs)-min(zs)+1 > expert['task']['depth']:
        raise ValueError(expert['name']+'超过厚度上限')
    if expert['name'] == '移动线21' and expert['task']['depth'] > 6:
        raise ValueError('移动线21厚度不得超过六格')


def require_all():
    experts = json.loads((ROOT/'experts.json').read_text())
    if {e['name'] for e in experts} != REQUIRED_NAMES or len(experts) != 18:
        raise ValueError('必须冻结全部18个专家需求，包含移动线21')
    for expert in experts:
        path = ROOT/'required'/(expert['id']+'.json')
        row = json.loads(path.read_text()) if path.exists() else {}
        require_case(expert,row)
    return experts
