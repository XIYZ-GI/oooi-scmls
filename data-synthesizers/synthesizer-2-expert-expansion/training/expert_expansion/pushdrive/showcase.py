"""挑选推驱课程代表结构并发布到网页结构库，默认只发布本体。"""

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path
from urllib.request import Request, urlopen

from ...serialization import digest, write_json
from .config import OUTPUT

AXES = ('x', 'y', 'z')


def load_rows(database):
    uri = 'file:%s?mode=ro' % Path(database).resolve()
    db = sqlite3.connect(uri, uri=True)
    try:
        return [json.loads(body) for (body,) in db.execute('SELECT body FROM records ORDER BY id')]
    finally:
        db.close()


def load_source(path):
    return json.loads(Path(path).read_text())


def profile(row):
    task, coverage = row['task'], row['coverage']
    area = task['width']*task['height']
    return dict(id=row['id'], category=coverage['category'], width=task['width'], height=task['height'],
                depth=coverage['actual_depth'], groups=coverage['groups'],
                targets=coverage['targets'], blocks=coverage['blocks'], area=area,
                density=round(coverage['targets']/max(1, area), 3), pulled=coverage['pulled'],
                stages=coverage['stages'], hooks=coverage['hooks'])


def select(rows, count):
    """每个类别优先取四格、目标多、密度高的结构，再按尺寸与时序补齐。"""
    profiles = {row['id']: profile(row) for row in rows}
    by_category = {}
    for row in rows:
        by_category.setdefault(profiles[row['id']]['category'], []).append(row)
    chosen, per_category = [], 2

    def add(entry_id):
        if entry_id and entry_id not in chosen and len(chosen) < count:
            chosen.append(entry_id)

    for category, group in sorted(by_category.items()):
        items = sorted((row['id'] for row in group),
                       key=lambda key: (profiles[key]['depth'] == 4, profiles[key]['pulled'] > 0,
                                        profiles[key]['targets'], profiles[key]['density'],
                                        profiles[key]['blocks']), reverse=True)
        picked = []
        for entry_id in items:
            shape = (profiles[entry_id]['width'], profiles[entry_id]['height'],
                     profiles[entry_id]['targets'])
            if any((profiles[k]['width'], profiles[k]['height'], profiles[k]['targets']) == shape
                   for k in picked):
                continue
            picked.append(entry_id)
            if len(picked) >= per_category:
                break
        for entry_id in picked:
            add(entry_id)
    while len(chosen) < min(count, len(rows)):
        remaining = [i for i in profiles if i not in chosen]
        sizes = {profiles[k]['area'] for k in chosen}
        depths = {profiles[k]['depth'] for k in chosen}
        add(max(remaining, key=lambda key: (profiles[key]['area'] not in sizes,
                                            profiles[key]['depth'] not in depths,
                                            profiles[key]['targets'], profiles[key]['density'])))
    return [row for row in rows if row['id'] in chosen]


def build_scenes(rows, tag):
    scenes, manifest = [], []
    for index, row in enumerate(rows, 1):
        item = profile(row)
        name = ('推驱课程·%s·%02d·%s·%dx%d·%d目标%d时序%d格'
                % (tag, index, item['category'], item['width'], item['height'],
                   item['targets'], item['groups'], item['depth']))
        scene_id = digest(['pushdrive-showcase', tag, row['id']])
        scenes.append(dict(id=scene_id, name=name+'·本体', blocks=row['proposal']['blocks']))
        manifest.append(dict(**item, name=name, push=row['proposal']['push'], scene=scene_id))
    return scenes, manifest


def publish(scenes, api):
    request = Request(api+'/scenes/migrate', data=json.dumps(dict(items=scenes)).encode(),
                      headers={'Content-Type': 'application/json'}, method='POST')
    with urlopen(request, timeout=120) as response:
        saved = json.load(response)['items']
    if len(saved) != len(scenes):
        raise ValueError('服务器返回的场景数量不符')
    key = lambda block: tuple(block['position'][a] for a in AXES)
    for expected, actual in zip(scenes, saved):
        with urlopen(api+'/scenes/'+actual['id'], timeout=60) as response:
            stored = json.load(response)
        if digest(sorted(stored['blocks'], key=key)) != digest(sorted(expected['blocks'], key=key)):
            raise ValueError('服务器结构与发布内容不一致：'+actual['name'])
    return saved


def publish_rows(rows, tag, count, api, output=None):
    selected = select(rows, count)
    scenes, manifest = build_scenes(selected, tag)
    saved = publish(scenes, api)
    for case, scene, actual in zip(manifest, scenes, saved):
        case['scene'] = dict(client_id=scene['id'], id=actual['id'], name=actual['name'],
                             revision=actual['revision'])
    payload = dict(tag=tag, count=len(manifest), cases=manifest, scenes=saved)
    if output:
        write_json(Path(output), payload)
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=OUTPUT/'records.sqlite3')
    parser.add_argument('--source', type=Path, help='直接读取预览产物 JSON 列表')
    parser.add_argument('--count', type=int, default=6)
    parser.add_argument('--tag', default='预览')
    parser.add_argument('--api', default='http://127.0.0.1:8010/api/datasets')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    rows = load_source(args.source) if args.source else load_rows(args.database)
    if not rows:
        parser.error('没有可发布的结构')
    payload = publish_rows(rows, args.tag, args.count, args.api, args.output)
    counts = Counter(case['category'] for case in payload['cases'])
    for case in payload['cases']:
        print('%s  本体%d块  尺寸%dx%d  厚度%d格  %d目标%d时序  密度%.2f  拉驱%d'
              % (case['name'], case['blocks'], case['width'], case['height'], case['depth'],
                 case['targets'], case['groups'], case['density'], case['pulled']))
    print(json.dumps(dict(published=len(payload['cases']), categories=dict(counts)),
                     ensure_ascii=False))


if __name__ == '__main__':
    main()
