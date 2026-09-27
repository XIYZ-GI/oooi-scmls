"""运行引擎能力及二进制指纹，供断点与性能报告核对。"""

import hashlib
from pathlib import Path

import mcscai_engine


def engine_identity():
    location = Path(mcscai_engine.__file__)
    binaries = [location] if location.suffix == '.so' else sorted(location.parent.glob('*.so'))
    return dict(version=mcscai_engine.__version__,
                generator_api=getattr(mcscai_engine,'__generator_api__',0),
                native_preflight=hasattr(mcscai_engine,'generator_preflight'),
                native_snapshot=hasattr(mcscai_engine.Simulator,'apply_native'),
                binaries={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in binaries})
