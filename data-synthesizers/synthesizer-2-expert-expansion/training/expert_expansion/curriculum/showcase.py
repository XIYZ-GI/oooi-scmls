"""从条件覆盖课程挑选代表结构，发布到网页三维结构库供人工查看。"""

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path
from urllib.request import Request, urlopen

from ...serialization import digest, write_json
from .config import OUTPUT

AXES = ('x', 'y', 'z')


def load_rows(path):
    """只读读取课程数据库中的全部已验收结构。"""
    uri = 'file:%s?mode=ro' % Path(path).resolve()
    db = sqlite3.connect(uri, uri=True)
    try:
        return [json.loads(body) for (body,) in db.execute('SELECT body FROM records ORDER BY id')]
    finally:
        db.close()


def profile(row):
    """提取用于挑选和命名展示结构的描述信息。"""
    task = row['task']
    blocks = row['proposal']['blocks']
    coverage = row['coverage']
    kinds = Counter(b['block']['kind'] for b in blocks)
    return dict(id=row['id'], width=task['width'], height=task['height'],
                depth=coverage['actual_depth'], allowed_depth=coverage['depth'],
                groups=coverage['groups'], targets=len(task['targets']), blocks=len(blocks),
                nodes=len(row['topology']), sticky=kinds.get('sticky_piston', 0),
                size=(task['width'], task['height']), materials=dict(kinds))


def select(rows, count):
    """先取各维度极值，再按尺寸、目标数量、时序和单元数的新颖度补齐。"""
    profiles = {row['id']: profile(row) for row in rows}
    chosen = []

    def add(entry_id):
        if entry_id and entry_id not in chosen and len(chosen) < count:
            chosen.append(entry_id)

    for metric in ('targets', 'blocks', 'nodes', 'sticky', 'groups', 'depth', 'width', 'height'):
        if profiles:
            add(max(profiles, key=lambda key: (profiles[key][metric], profiles[key]['blocks'])))
    counts = Counter((p['size'], p['depth'], p['groups']) for p in profiles.values())
    while len(chosen) < min(count, len(profiles)):
        best, best_score = None, None
        for entry_id, item in profiles.items():
            if entry_id in chosen:
                continue
            novelty = (8 * (item['size'] not in {profiles[k]['size'] for k in chosen})
                       + 4 * (item['targets'] not in {profiles[k]['targets'] for k in chosen})
                       + 3 * (item['depth'] not in {profiles[k]['depth'] for k in chosen})
                       + 2 * (item['groups'] not in {profiles[k]['groups'] for k in chosen})
                       + 2 * (item['nodes'] not in {profiles[k]['nodes'] for k in chosen})
                       + 2 * (item['sticky'] != 0 and all(profiles[k]['sticky'] for k in chosen))
                       + 1 / counts[(item['size'], item['depth'], item['groups'])]
                       + item['blocks'] / 100)
            if best_score is None or novelty > best_score:
                best, best_score = entry_id, novelty
        add(best)
    return [row for row in rows if row['id'] in chosen]


def build_scenes(rows, tag, body_only=False):
    """为每个结构生成场景；body_only 为真时只发布本体，不带十负载。"""
    scenes, manifest = [], []
    for index, row in enumerate(rows, 1):
        item = profile(row)
        task, proposal = row['task'], row['proposal']
        name = ('课程结构·%s·%02d·%dx%d·%d目标%d时序%d格'
                % (tag, index, item['width'], item['height'], item['targets'], item['groups'], item['depth']))
        variants = [('本体', proposal['blocks'])]
        if not body_only:
            loads = [dict(position=dict(x=t['x'], y=t['y'], z=t['z'] + offset),
                          block=dict(kind='iron_block', facing='positive_z'))
                     for t in task['targets'] for offset in range(10)]
            actuator = dict(position={**proposal['push'], 'z': proposal['push']['z'] - 1},
                            block=dict(kind='piston', facing='positive_z'))
            variants.append(('十负载', [*proposal['blocks'], *loads, actuator]))
        case = dict(**item, name=name, push=proposal['push'],
                    ticks=sorted({t['order'] for t in task['targets']}), scenes=[])
        for suffix, blocks in variants:
            scene = dict(id=digest(['curriculum-showcase', tag, row['id'], suffix]),
                         name=name + '·' + suffix, blocks=blocks)
            case['scenes'].append(dict(key=scene['id'], name=scene['name']))
            scenes.append(scene)
        manifest.append(case)
    return scenes, manifest


def publish(scenes, api):
    """写入服务器结构库并逐条回读校验，避免只写不验。"""
    request = Request(api + '/scenes/migrate', data=json.dumps(dict(items=scenes)).encode(),
                      headers={'Content-Type': 'application/json'}, method='POST')
    with urlopen(request, timeout=120) as response:
        saved = json.load(response)['items']
    if len(saved) != len(scenes):
        raise ValueError('服务器返回的场景数量不符')
    key = lambda block: tuple(block['position'][a] for a in AXES)
    for expected, actual in zip(scenes, saved):
        with urlopen(api + '/scenes/' + actual['id'], timeout=60) as response:
            stored = json.load(response)
        if digest(sorted(stored['blocks'], key=key)) != digest(sorted(expected['blocks'], key=key)):
            raise ValueError('服务器结构与发布内容不一致：' + actual['name'])
    return saved


def published_ids(directory):
    """收集此前发布记录里的结构 id，避免重复发布同一结构。"""
    ids = set()
    for path in Path(directory).glob('showcase*.json'):
        try:
            payload = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        for case in payload.get('cases', []):
            if case.get('id'):
                ids.add(case['id'])
    return ids


def apply_filters(rows, args):
    """按面积、目标数量和密度筛选，用于专门查看密集或小截面结构。"""
    selected = []
    for row in rows:
        item = profile(row)
        area = item['width'] * item['height']
        density = item['targets'] / area
        if args.max_area and area > args.max_area:
            continue
        if args.min_area and area < args.min_area:
            continue
        if args.min_targets and item['targets'] < args.min_targets:
            continue
        if args.min_density and density < args.min_density:
            continue
        selected.append(row)
    return selected


def order_rows(rows, order):
    """按密度、面积或目标数量排序；默认交给新颖度挑选。"""
    profiles = {row['id']: profile(row) for row in rows}
    if order == 'density':
        key = lambda row: (-profiles[row['id']]['targets'] / (profiles[row['id']]['width'] * profiles[row['id']]['height']),
                           -profiles[row['id']]['targets'], profiles[row['id']]['blocks'])
    elif order == 'area':
        key = lambda row: (profiles[row['id']]['width'] * profiles[row['id']]['height'],
                           -profiles[row['id']]['targets'])
    elif order == 'targets':
        key = lambda row: (-profiles[row['id']]['targets'], profiles[row['id']]['blocks'])
    else:
        return None
    return sorted(rows, key=key)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=OUTPUT / 'records.sqlite3')
    parser.add_argument('--count', type=int, default=8)
    parser.add_argument('--tag', default='v3')
    parser.add_argument('--api', default='http://127.0.0.1:8010/api/datasets')
    parser.add_argument('--max-area', type=int, default=0, help='只看截面面积不超过该值的结构')
    parser.add_argument('--min-area', type=int, default=0, help='只看截面面积不小于该值的结构')
    parser.add_argument('--min-targets', type=int, default=0, help='只看目标数不少于该值的结构')
    parser.add_argument('--min-density', type=float, default=0.0, help='只看每格截面目标数不低于该值的结构')
    parser.add_argument('--body-only', action='store_true', help='只发布本体，不带十负载场景')
    parser.add_argument('--exclude-published', action='store_true', help='跳过此前已发布过的结构')
    parser.add_argument('--order', choices=('diversity', 'density', 'area', 'targets'),
                        default='diversity', help='挑选顺序，默认按尺寸与时序新颖度')
    args = parser.parse_args()
    if args.count < 1:
        parser.error('展示数量必须大于零')
    rows = apply_filters(load_rows(args.database), args)
    if args.exclude_published:
        known = published_ids(args.database.parent)
        rows = [row for row in rows if row['id'] not in known]
    if not rows:
        parser.error('没有满足面积、目标数量或密度条件的结构')
    ordered = order_rows(rows, args.order)
    selected = ordered[:args.count] if ordered else select(rows, args.count)
    scenes, manifest = build_scenes(selected, args.tag, args.body_only)
    saved = publish(scenes, args.api)
    stored = {scene['id']: scene for scene in saved}
    for case in manifest:
        case['scenes'] = [dict(id=item['key'], name=item['name'],
                               stored_id=stored[item['key']]['id'] if item['key'] in stored else item['key'])
                          for item in case['scenes']]
    write_json(OUTPUT / ('showcase-%s.json' % args.tag), dict(database=str(args.database), tag=args.tag,
                                                             cases=manifest, scenes=saved))
    for index, case in enumerate(manifest, 1):
        area = case['width'] * case['height']
        print('%d. %s  本体%d块  目标%d/面积%d=%.2f  时序%s'
              % (index, case['name'], case['blocks'], case['targets'], area,
                 case['targets'] / area, case['ticks']))


if __name__ == '__main__':
    main()
