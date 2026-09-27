"""缓存由需求和局部库枚举的放置；构造规则变动后自动失效。"""

import gzip
import inspect
import json
from pathlib import Path

from ..serialization import digest
from .config import ROOT
from .placements import placements
from .signals import output_power


def candidates(task, modules, complete_outputs=True):
    source = Path(__file__).parent
    signature = digest([task, modules, complete_outputs, inspect.getsource(output_power),
                        [(name, (source/name).read_text()) for name in
                        ('placements.py','modules.py','transport.py')]])
    path = ROOT/'placements'/(signature+'.json.gz')
    if path.exists():
        with gzip.open(path, 'rt') as handle:
            return json.load(handle)
    nodes = list(placements(task, modules,complete_outputs=complete_outputs))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    with gzip.open(temporary, 'wt', compresslevel=1) as handle:
        json.dump(nodes, handle, separators=(',', ':'))
    temporary.replace(path)
    return nodes
