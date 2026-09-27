"""事务保存课程、全局重复预算和隔离划分；中断后从数据库恢复。"""

from collections import Counter
import json
import sqlite3

from ...reinforcement.demands import geometry
from ...serialization import digest, write_json
from ..dataset import compact
from .config import EXACT_CAP, GEOMETRY_CAP, POSITION_CAP, SKELETON_CAP, HOLDOUT_PER_CELL, quotas


def partition(key):
    n = int(digest(['balanced-curriculum', key])[:8], 16) % 10
    return 'development' if n == 0 else 'heldout' if n == 1 else 'train'


class Repository:
    def __init__(self, output, excluded):
        self.output, self.excluded = output, excluded
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
        self.counts, self.sizes, self.targets, self.actual, self.dimensions = (Counter() for _ in range(5))
        self.buckets = Counter()
        for split, cell, exact, geom, pos, skeleton, coverage in self.db.execute(
                'SELECT split,cell,exact,geometry,positions,skeleton,coverage FROM records'):
            self.track(split, cell, exact, geom, pos, skeleton, json.loads(coverage))
        saved = self.db.execute("SELECT value FROM state WHERE key='progress'").fetchone()
        self.state = json.loads(saved[0]) if saved else dict(next_index=0, reasons={}, attempts=0)
        self.goals = quotas()

    def track(self, split, cell, exact, geom, pos, skeleton, coverage):
        for counter, key in ((self.exact, exact), (self.geometries, geom),
                             (self.positions, pos), (self.skeletons, skeleton)):
            counter[key] += 1
        self.counts[f'{split}/{cell}'] += 1
        self.sizes[f'{split}/{cell}/{coverage["size"]}'] += 1
        self.targets[f'{split}/{cell}/{coverage["targets"]}'] += 1
        self.buckets[f'{cell}/{coverage["size"]}/{coverage["targets"]}'] += 1
        self.actual[f'{split}/{cell}/{coverage["actual_depth"]}'] += 1
        self.dimensions[f'{coverage["width"]}x{coverage["height"]}'] += 1

    def add(self, row):
        task, coverage = row['task'], row['coverage']
        geom = geometry(task)
        pos = geometry({**task, 'targets': [{**t, 'order': 1} for t in task['targets']]})
        exact = digest(sorted((t['x'], t['y'], t['z'], t['order']) for t in task['targets']))
        skeleton = row['group']
        if geom in self.excluded or pos in self.excluded:
            return '专家或保留需求排除'
        split = partition(skeleton)
        if partition(geom) != split or partition(pos) != split:
            return '骨架及目标几何跨划分隔离'
        for count, limit, reason in ((self.exact[exact], EXACT_CAP, '相同目标及时序重复上限'),
                                    (self.geometries[geom], GEOMETRY_CAP, '对称等价目标重复上限'),
                                    (self.positions[pos], POSITION_CAP, '忽略时序的目标布局重复上限'),
                                    (self.skeletons[skeleton], SKELETON_CAP, '连接骨架重复上限')):
            if count >= limit:
                return reason
        cell = f'{coverage["depth"]}:{coverage["groups"]}'
        goal = self.goals[cell] if split == 'train' else HOLDOUT_PER_CELL
        if self.counts[f'{split}/{cell}'] >= goal:
            return '厚度时序配额已满'
        # 不让容易生成的小截面、少目标或单一实际厚度占满一个条件组合。
        for counter, key, ratio, reason in (
                (self.sizes, f'{split}/{cell}/{coverage["size"]}', .6, '单一尺寸类别占比上限'),
                (self.targets, f'{split}/{cell}/{coverage["targets"]}', .6, '单一目标数量类别占比上限'),
                (self.actual, f'{split}/{cell}/{coverage["actual_depth"]}', .75, '单一实际厚度占比上限')):
            if counter[key] >= max(1, int(goal*ratio)):
                # 上限为两格时允许实际两格占满，避免人为要求一格答案。
                if reason == '单一实际厚度占比上限' and coverage['depth'] == 2:
                    continue
                return reason
        row.update(split=split, usage='fit' if split == 'train' else split, geometry=geom,
                   task_id=digest(task)[:24], family=f'groups{coverage["groups"]}_depth{coverage["depth"]}')
        evidence = {k: row['evaluation'][k] for k in
                    ('engine_version', 'load_blocks', 'simulated_ticks', 'observed_order')
                    if k in row['evaluation']}
        row = compact(row)
        row['evaluation'].update(evidence)
        cursor = self.db.execute('INSERT OR IGNORE INTO records VALUES (?,?,?,?,?,?,?,?,?)',
            (row['id'], split, cell, exact, geom, pos, skeleton, json.dumps(coverage, ensure_ascii=False),
             json.dumps(row, ensure_ascii=False, separators=(',', ':'))))
        if not cursor.rowcount:
            return '结构记录完全重复'
        self.track(split, cell, exact, geom, pos, skeleton, coverage)
        return '课程已保存'

    def checkpoint(self, state, status):
        self.state = state
        self.db.execute("INSERT OR REPLACE INTO state VALUES ('progress',?)", (json.dumps(state),))
        self.db.commit()
        report = dict(**state, status=status, training_started=False, train_target=sum(self.goals.values()),
                      counts=dict(self.counts), quotas=self.goals, sizes=dict(self.sizes),
                      target_counts=dict(self.targets), actual_depths=dict(self.actual),
                      dimensions=dict(self.dimensions), exact_targets=len(self.exact),
                      target_geometries=len(self.geometries), position_geometries=len(self.positions),
                      skeletons=len(self.skeletons), records=sum(self.counts.values()),
                      train_records=sum(v for k, v in self.counts.items() if k.startswith('train/')),
                      max_repeats=dict(exact=max(self.exact.values(), default=0),
                                       geometry=max(self.geometries.values(), default=0),
                                       positions=max(self.positions.values(), default=0),
                                       skeleton=max(self.skeletons.values(), default=0)))
        write_json(self.output/'progress.json', report)
        return report

    def complete(self):
        return all(self.counts[f'{split}/{cell}'] >= (goal if split == 'train' else HOLDOUT_PER_CELL)
                   for cell, goal in self.goals.items() for split in ('train', 'development', 'heldout'))

    def export(self):
        for split, filename in [('train', 'train-5x.jsonl'), ('development', 'development.jsonl'),
                                ('heldout', 'heldout.jsonl')]:
            path = self.output/filename
            temporary = path.with_suffix('.tmp')
            with temporary.open('w') as stream:
                for body, in self.db.execute('SELECT body FROM records WHERE split=? ORDER BY id', (split,)):
                    stream.write(body+'\n')
            temporary.replace(path)
