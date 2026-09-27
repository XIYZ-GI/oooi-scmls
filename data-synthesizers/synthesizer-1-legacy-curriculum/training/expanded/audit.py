"""训练前核对新骨架、目标几何与继承模型历史数据的交叉。"""

from collections import Counter
from pathlib import Path

from ..data import read_examples
from ..compact_round2.rules import geometry
from ..compact_round2.prepare import write_rows
from ..serialization import digest, write_json


def main():
    root = Path('data/generation/stage4')
    past = set()
    for directory in ('stage1', 'stage2', 'stage3', 'stage3-round2', 'stage3-coverage', 'stage3-balanced'):
        for path in (root.parent/directory).glob('*.jsonl'):
            for row in read_examples(path):
                if 'task' in row:
                    past.add(geometry(row['task']))
    records = read_examples(root/'examples.jsonl')
    train = [r for r in records if r['usage'] == 'fit']
    development = read_examples(root/'development.jsonl')
    heldout = read_examples(root/'heldout.jsonl')
    removed = [r['task_id'] for r in heldout if geometry(r['task']) in past]
    heldout = [r for r in heldout if geometry(r['task']) not in past]
    fit_groups = {r['group'] for r in train if r['source'] == 'alternating_pull_path_v1'}
    dev_groups = {r['group'] for r in development if r['source'] == 'alternating_pull_path_v1'}
    test_groups = {r['group'] for r in heldout}
    assert not fit_groups & test_groups
    assert not dev_groups & test_groups
    fit_geo = {geometry(r['task']) for r in train}
    dev_geo = {geometry(r['task']) for r in development}
    assert not {geometry(r['task']) for r in heldout} & (fit_geo | dev_geo)
    write_rows(root/'heldout.jsonl', heldout)
    write_json(root/'split-audit.json', {'removed_previously_seen_tasks': removed,
        'counts': dict(Counter(r['family'] for r in heldout)), 'historical_geometries': len(past),
        'heldout_sha256': digest((root/'heldout.jsonl').read_text()),
        'fit_heldout_topology_overlap': 0, 'development_heldout_topology_overlap': 0,
        'fit_development_heldout_geometry_overlap': 0,
        'note': '连接骨架整体保留，不把镜像或材料替换当作独立来源。所用拉驱构造法仍共享，不声称跨未知原理。'})
    print((root/'split-audit.json').read_text())


if __name__ == '__main__':
    main()
