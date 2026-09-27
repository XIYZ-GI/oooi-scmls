"""挑选不同功能与厚度的代表结构，仅将本体发布到服务器结构。"""

import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen

from ..serialization import digest, write_json
from .config import CATEGORIES, DEPTHS, NAME
from .geometry import point
from .reduction import reduce
from .verification import verify_pulls


def select(rows, count):
    chosen, seen = [], set()
    def score(row):
        c, m = row['coverage'], row['mechanisms']
        return (c['targets'], m['unused_observers'] == 0,
                m['secondary_useful_lateral_observers'], m['max_charged_per_motion'],
                c['density'], -c['blocks'])
    def pick(pool, required=lambda _: True):
        for row in sorted(pool, key=score, reverse=True):
            if row['skeleton'] in seen:
                continue
            selected, reason = reduce(row)
            if reason or selected['skeleton'] in seen or not required(selected):
                continue
            checks, reason = verify_pulls(selected)
            if reason:
                continue
            selected['pull_ablation'] = checks
            chosen.append(selected)
            seen.update((row['skeleton'], selected['skeleton']))
            return

    cells = [(c, d) for d in DEPTHS for c in CATEGORIES if c != '多目标同推' or d == 4]
    for category, depth in cells:
        pick([r for r in rows if r['family'] == category and r['task']['depth'] == depth])
        if len(chosen) >= count:
            break
    features = [lambda r: r['task']['depth'] == 4 and r['family'] == '多目标同推'
                and r['mechanisms']['secondary_useful_lateral_observers'] >= 3
                and r['mechanisms']['secondary_useful_lateral_observers'] >=
                .8*r['mechanisms']['secondary_observers'],
                lambda r: r['task']['depth'] == 3 and r['coverage']['groups'] >= 3,
                lambda r: r['task']['depth'] == 4 and r['coverage']['groups'] >= 3,
                lambda r: r['task']['depth'] == 4 and r['mechanisms']['extended_input_pulls'] > 0,
                lambda r: r['task']['depth'] == 2 and r['mechanisms'].get('saturated_extension_pulls', 0) > 0,
                lambda r: r['task']['depth'] == 2 and r['mechanisms']['extended_input_pulls'] > 0]
    for feature in features:
        if len(chosen) >= count:
            break
        if not any(feature(r) for r in chosen):
            pick([r for r in rows if feature(r)], feature)
    while len(chosen) < min(count, len(rows)):
        before = len(chosen)
        pick(rows)
        if len(chosen) == before:
            break
    return chosen


def publish(rows, tag, api, directory):
    items, cases = [], []
    for index, row in enumerate(rows, 1):
        c = row['coverage']
        name = (f"移动线数据集·{tag}·{index:02d}·{c['actual_depth']}格·{c['category']}·"
                f"{c['width']}×{c['height']}·{c['targets']}目标{c['groups']}时序·本体")
        client_id = digest(['moving-line-generator', tag, row['id']])
        items.append(dict(id=client_id, name=name, blocks=row['proposal']['blocks']))
        cases.append(dict(record=row['id'], name=name, coverage=c, push=row['proposal']['push'],
                          targets=row['task']['targets'], mechanisms=row['mechanisms'],
                          rounds=row['evaluation']['rounds'], pull_ablation=row['pull_ablation'],
                          reduction=row['reduction']))
    request = Request(api+'/scenes/migrate', data=json.dumps(dict(items=items)).encode(),
                      headers={'Content-Type': 'application/json'}, method='POST')
    with urlopen(request, timeout=120) as response:
        saved = json.load(response)['items']
    if len(saved) != len(items):
        raise ValueError('服务器返回数量与发布数量不一致')
    for expected, actual, case in zip(items, saved, cases):
        with urlopen(api+'/scenes/'+actual['id'], timeout=60) as response:
            stored = json.load(response)
        key = lambda b: point(b['position'])
        if digest(sorted(stored['blocks'], key=key)) != digest(sorted(expected['blocks'], key=key)):
            raise ValueError('服务器保存的本体与已验证结构不一致')
        case['scene'] = dict(id=actual['id'], name=actual['name'], revision=actual['revision'])
    value = dict(generator=NAME, tag=tag, cases=cases)
    write_json(directory/f'showcase-{tag}.json', value)
    write_json(directory/f'showcase-{tag}-records.json', rows)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--count', type=int, default=12)
    parser.add_argument('--tag', default='新方案首批')
    parser.add_argument('--api', default='http://127.0.0.1:8010/api/datasets')
    parser.add_argument('--publish', action='store_true')
    parser.add_argument('--focus', choices=('balanced','dense'), default='balanced')
    parser.add_argument('--extension-share',type=float,default=.7)
    args = parser.parse_args()
    if args.count < 1:
        parser.error('展示数量必须大于零')
    if not 0 <= args.extension_share <= 1:
        parser.error('入口延伸展示比例必须在零至一之间')
    candidates = json.loads(args.source.read_text())
    if args.focus == 'dense':
        from .dense_showcase import select as select_dense
        rows = select_dense(candidates,args.count,args.extension_share)
    else:
        rows = select(candidates,args.count)
    if not rows:
        parser.error('没有通过展示检查的结构')
    write_json(args.source.parent/'selected.json', rows)
    if args.publish:
        result = publish(rows, args.tag, args.api, args.source.parent)
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(json.dumps([r['coverage'] for r in rows], ensure_ascii=False))


if __name__ == '__main__':
    main()
