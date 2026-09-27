"""冻结训练侧源码与本机引擎，使长期任务不受工作区后续编辑影响。"""

import argparse
from pathlib import Path
import shutil
import tempfile

import mcscai_engine

from ...serialization import digest, write_json
from ..runtime import engine_identity


def freeze(output):
    output = Path(output).resolve()
    destination = output/'runtime'
    if destination.exists():
        raise ValueError('运行快照已存在，不能覆盖正在使用或用于断点恢复的源码')
    root = Path(__file__).resolve().parents[2]
    sources = {str(p.relative_to(root)): p.read_text() for p in sorted(root.rglob('*.py'))
               if 'tests' not in p.parts and '__pycache__' not in p.parts}
    output.mkdir(parents=True, exist_ok=True)
    engine_file = Path(mcscai_engine.__file__).resolve()
    with tempfile.TemporaryDirectory(prefix='.freeze-', dir=output) as temporary:
        staging = Path(temporary)/'runtime'
        for relative, content in sources.items():
            path = staging/'training'/relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        if engine_file.name == '__init__.py':
            shutil.copytree(engine_file.parent, staging/'mcscai_engine',
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        else:
            shutil.copy2(engine_file, staging/engine_file.name)
        manifest = dict(source_digest=digest(sources), files=len(sources), engine=engine_identity())
        write_json(staging/'freeze.json', manifest)
        staging.rename(destination)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    manifest = freeze(args.output)
    print(f"已冻结{manifest['files']}个源码文件及引擎：{args.output/'runtime'}")


if __name__ == '__main__':
    main()
