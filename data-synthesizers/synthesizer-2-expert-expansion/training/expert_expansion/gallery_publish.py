"""从随机成功产物选择不同连接骨架并发布服务器三维结构。"""

from collections import Counter
import json
from urllib.request import Request, urlopen

from ..reinforcement.demands import geometry
from ..serialization import digest, write_json


def describe(row):
    task = row['task']
    blocks = row['proposal']['blocks']
    kinds = Counter(b['block']['kind'] for b in blocks)
    return dict(id=row['id'], width=task['width'], height=task['height'], depth=task['depth'],
                targets=len(task['targets']), groups=len({t['order'] for t in task['targets']}),
                blocks=len(blocks), nodes=len(row['topology']),
                branches=sum(n['branches'] > 1 for n in row['topology']),
                materials=dict(kinds), group=row['group'], geometry=geometry(task),
                ticks=sorted(set(row['evaluation']['rounds'][0]['ticks'])))


def select(rows, count):
    # 先保留实际规模极值，再按新增单元、骨架、材料和目标几何补齐；没有预设需求档位。
    unique = {r['id']: r for r in rows}
    stats = {key: describe(r) for key, r in unique.items()}
    selected = []
    def add(key):
        if key not in selected and len(selected) < count:
            selected.append(key)
    for metric in ('targets', 'groups', 'nodes', 'branches', 'width', 'height', 'depth'):
        if stats:
            add(max(stats, key=lambda key: (stats[key][metric], stats[key]['blocks'])))
    if stats:
        add(min(stats, key=lambda key: stats[key]['blocks']))
    while len(selected) < min(count, len(unique)):
        modules = {n['module'] for key in selected for n in unique[key]['topology']}
        groups = {stats[key]['group'] for key in selected}
        geometries = {stats[key]['geometry'] for key in selected}
        materials = {tuple(sorted(stats[key]['materials'])) for key in selected}
        def novelty(key):
            s = stats[key]
            return (s['group'] not in groups, s['geometry'] not in geometries,
                    len({n['module'] for n in unique[key]['topology']}-modules),
                    tuple(sorted(s['materials'])) not in materials, s['branches'], s['blocks'])
        add(max((key for key in unique if key not in selected), key=novelty))
    return [unique[key] for key in selected]


def publish(rows, output, seed, api):
    scenes, manifest = [], []
    for index, row in enumerate(rows, 1):
        summary = describe(row)
        task, proposal = row['task'], row['proposal']
        prefix = (f"随机课程·{seed}·{index:02d}·{summary['targets']}目标"
                  f"{summary['groups']}时序{summary['depth']}格")
        loads = [dict(position=dict(x=t['x'], y=t['y'], z=t['z']+i),
                      block=dict(kind='iron_block', facing='positive_z'))
                 for t in task['targets'] for i in range(10)]
        actuator = dict(position={**proposal['push'], 'z': proposal['push']['z']-1},
                        block=dict(kind='piston', facing='positive_z'))
        for suffix, blocks in [('本体', proposal['blocks']), ('十负载', [*proposal['blocks'], *loads, actuator])]:
            scenes.append(dict(id=digest(['random-gallery', seed, row['id'], suffix]),
                               name=prefix+'·'+suffix, blocks=blocks))
        path = output/f'{index:02d}.json'
        write_json(path, row)
        manifest.append(dict(**summary, name=prefix, path=str(path), push=proposal['push']))
    if not scenes:
        write_json(output/'published.json', dict(cases=[], scenes=[]))
        return []
    request = Request(api+'/scenes/migrate', data=json.dumps(dict(items=scenes)).encode(),
                      headers={'Content-Type': 'application/json'}, method='POST')
    with urlopen(request, timeout=60) as response:
        saved = json.load(response)['items']
    if len(saved) != len(scenes):
        raise ValueError('服务器返回的场景数量不符')
    for expected, actual in zip(scenes, saved):
        with urlopen(api+'/scenes/'+actual['id'], timeout=30) as response:
            stored = json.load(response)
        key = lambda b: tuple(b['position'][a] for a in ('x', 'y', 'z'))
        if digest(sorted(stored['blocks'], key=key)) != digest(sorted(expected['blocks'], key=key)):
            raise ValueError('服务器结构与生成产物不一致：'+actual['name'])
    for i, case in enumerate(manifest):
        case['scenes'] = [dict(id=s['id'], name=s['name']) for s in saved[2*i:2*i+2]]
    write_json(output/'published.json', dict(cases=manifest,
        scenes=[{k: s[k] for k in ('id', 'name', 'revision')} for s in saved]))
    return manifest
