"""推驱课程的事务保存、重复上限、隔离划分与断点恢复。"""

from collections import Counter
import json
import sqlite3

from ...reinforcement.demands import geometry
from ...serialization import digest, write_json
from ..dataset import compact
from .config import (CATEGORIES, EXACT_CAP, GEOMETRY_CAP, POSITION_CAP, SKELETON_CAP,
                     TOTAL_RECORDS, quota_table)


def partition(key):
    bucket = int(digest(['pushdrive-curriculum', key])[:8], 16) % 20
    return 'development' if bucket == 0 else 'heldout' if bucket == 1 else 'train'


class Repository:
    def __init__(self, output):
        self.output = output
        self.db = sqlite3.connect(output/'records.sqlite3')
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS records (
                id TEXT PRIMARY KEY, split TEXT, cell TEXT, exact TEXT, geometry TEXT,
                positions TEXT, skeleton TEXT, coverage TEXT, body TEXT);
            CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS failures (reason TEXT PRIMARY KEY, body TEXT);
        ''')
        self.exact, self.geometries, self.positions, self.skeletons = (Counter() for _ in range(4))
        self.counts, self.actual, self.depths, self.hooks = (Counter() for _ in range(4))
        for split, cell, exact, geom, pos, skeleton, coverage in self.db.execute(
                'SELECT split,cell,exact,geometry,positions,skeleton,coverage FROM records'):
            self.track(split, cell, exact, geom, pos, skeleton, json.loads(coverage))
        saved = self.db.execute("SELECT value FROM state WHERE key='progress'").fetchone()
        self.state = json.loads(saved[0]) if saved else dict(next_index=0, reasons={}, attempts=0)
        self.goals = quota_table()

    def track(self, split, cell, exact, geom, pos, skeleton, coverage):
        for counter, key in ((self.exact, exact), (self.geometries, geom),
                             (self.positions, pos), (self.skeletons, skeleton)):
            counter[key] += 1
        self.counts['%s/%s' % (split, cell)] += 1
        self.actual['%s/%s/%d时序' % (split, cell, coverage['groups'])] += 1
        self.depths['%s/%s/%d格' % (split, cell, coverage['depth'])] += 1
        self.hooks['%s/%s/%s拉驱' % (split, cell, '有' if coverage['pulled'] else '无')] += 1

    def add(self, row):
        task, coverage = row['task'], row['coverage']
        key = (coverage['category'], coverage['size'], coverage['targets_band'])
        cell = '%s/%s/%s' % key
        geom = geometry(task)
        pos = geometry({**task, 'targets': [{**t, 'order': 1} for t in task['targets']]})
        exact = digest(sorted((t['x'], t['y'], t['z'], t['order']) for t in task['targets']))
        skeleton = row['group']
        split = partition(skeleton)
        if partition(geom) != split or partition(pos) != split:
            return '骨架与目标几何跨划分隔离'
        for count, limit, reason in ((self.exact[exact], EXACT_CAP, '相同目标及时序重复上限'),
                                     (self.geometries[geom], GEOMETRY_CAP, '对称等价目标重复上限'),
                                     (self.positions[pos], POSITION_CAP, '忽略时序的目标布局重复上限'),
                                     (self.skeletons[skeleton], SKELETON_CAP, '连接骨架重复上限')):
            if count >= limit:
                return reason
        goal = self.goals[cell] if split == 'train' else max(4, self.goals[cell]//8)
        if self.counts['%s/%s' % (split, cell)] >= goal:
            return '类别尺寸目标配额已满'
        row.update(split=split, usage='fit' if split == 'train' else split,
                   geometry=geom, task_id=digest(task)[:24], cell=cell)
        row = compact(row)
        cursor = self.db.execute('INSERT OR IGNORE INTO records VALUES (?,?,?,?,?,?,?,?,?)',
                                 (row['id'], split, cell, exact, geom, pos, skeleton,
                                  json.dumps(coverage, ensure_ascii=False),
                                  json.dumps(row, ensure_ascii=False, separators=(',', ':'))))
        if not cursor.rowcount:
            return '结构记录完全重复'
        self.track(split, cell, exact, geom, pos, skeleton, coverage)
        return '课程已保存'

    def checkpoint(self, state, status):
        self.state = state
        self.db.execute("INSERT OR REPLACE INTO state VALUES ('progress',?)", (json.dumps(state),))
        self.db.commit()
        per_category = Counter()
        for key, value in self.counts.items():
            split, cell = key.split('/', 1)
            if split == 'train':
                per_category[cell.split('/')[0]] += value
        report = dict(**state, status=status, train_target=TOTAL_RECORDS,
                      categories=dict(CATEGORIES), category_progress=dict(per_category),
                      records=sum(self.counts.values()),
                      train_records=sum(v for k, v in self.counts.items() if k.startswith('train/')),
                      actual_groups=dict(self.actual), depths=dict(self.depths),
                      pulls=dict(self.hooks), cells=dict(self.counts),
                      max_repeats=dict(exact=max(self.exact.values(), default=0),
                                       geometry=max(self.geometries.values(), default=0),
                                       positions=max(self.positions.values(), default=0),
                                       skeleton=max(self.skeletons.values(), default=0)))
        write_json(self.output/'progress.json', report)
        return report

    def complete(self):
        return all(self.counts['train/%s' % cell] >= goal for cell, goal in self.goals.items())

    def export(self):
        for split, filename in (('train', 'train.jsonl'), ('development', 'development.jsonl'),
                                ('heldout', 'heldout.jsonl')):
            path = self.output/filename
            temporary = path.with_suffix('.tmp')
            with temporary.open('w') as stream:
                for body, in self.db.execute('SELECT body FROM records WHERE split=? ORDER BY id',
                                             (split,)):
                    stream.write(body+'\n')
            temporary.replace(path)
