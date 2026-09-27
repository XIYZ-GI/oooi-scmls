"""事务保存候选、失败统计和断点；几何等价结构只保留一份。"""

from collections import Counter
import json
import sqlite3
import time

from ..serialization import write_json
from .config import NAME


class Repository:
    def __init__(self, directory, identity, batch_size=32, flush_interval=1.0):
        if batch_size < 1 or flush_interval <= 0:
            raise ValueError('事务批量和刷新间隔必须为正')
        self.batch_size, self.flush_interval = batch_size, flush_interval
        self.pending = 0
        self.last_flush = time.monotonic()
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(directory/'records.sqlite3')
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS attempts (
                id INTEGER PRIMARY KEY, category TEXT, depth INTEGER, reason TEXT);
            CREATE TABLE IF NOT EXISTS records (
                id TEXT PRIMARY KEY, signature TEXT UNIQUE, category TEXT,
                depth INTEGER, skeleton TEXT, body TEXT NOT NULL);
        ''')
        saved = self.db.execute("SELECT body FROM metadata WHERE key='identity'").fetchone()
        if saved and json.loads(saved[0]) != identity:
            self.db.close()
            raise ValueError('本目录的源码或运行参数不同，请使用新的输出目录，避免混合验证协议')
        self.db.execute("INSERT OR IGNORE INTO metadata VALUES ('identity',?)",
                        (json.dumps(identity, ensure_ascii=False),))
        self.identity = identity
        self.counts = Counter({(c, d): n for c, d, n in self.db.execute(
            'SELECT category,depth,COUNT(*) FROM records GROUP BY category,depth')})
        self.extension_counts = self._extension_counts()
        self.completed = {i for i, in self.db.execute('SELECT id FROM attempts')}
        self.db.commit()

    def save(self, result, quota):
        query = result['requested']
        key = query['category'], query['depth']
        reason = result['reason']
        row = result.get('row')
        try:
            if row and self.counts[key] >= quota[key]:
                reason = '本类别厚度的预览配额已满'
            elif row:
                cursor = self.db.execute('INSERT OR IGNORE INTO records VALUES (?,?,?,?,?,?)',
                    (row['id'], row['canonical'], *key, row['skeleton'],
                     json.dumps(row, ensure_ascii=False, separators=(',', ':'))))
                if cursor.rowcount:
                    self.counts[key] += 1
                    if row.get('mechanisms',{}).get('extended_input_pulls',0)>0:
                        self.extension_counts[key] += 1
                    reason = '已保存'
                else:
                    reason = '对称或材料互换等价结构重复'
            self.db.execute('INSERT INTO attempts VALUES (?,?,?,?)', (result['index'], *key, reason))
            self.completed.add(result['index'])
            self.pending += 1
            self.flush_due()
        except Exception:
            self.db.rollback()
            self.counts = Counter({(c,d):n for c,d,n in self.db.execute(
                'SELECT category,depth,COUNT(*) FROM records GROUP BY category,depth')})
            self.extension_counts = self._extension_counts()
            self.completed = {i for i, in self.db.execute('SELECT id FROM attempts')}
            self.pending = 0
            raise

    def flush_due(self):
        if self.pending >= self.batch_size or time.monotonic()-self.last_flush >= self.flush_interval:
            self.flush()

    def flush(self):
        if self.pending:
            self.db.commit()
            self.pending = 0
        self.last_flush = time.monotonic()

    def rows(self):
        return [json.loads(b) for b, in self.db.execute('SELECT body FROM records ORDER BY id')]

    def _extension_counts(self):
        return Counter({(c,d):n for c,d,n in self.db.execute('''
            SELECT category,depth,COUNT(*) FROM records
            WHERE json_extract(body,'$.mechanisms.extended_input_pulls') > 0
            GROUP BY category,depth''')})

    def report(self, status, quota, export_records=True):
        self.flush()
        rows = self.rows() if export_records else [dict(coverage=json.loads(c)) for c, in self.db.execute(
            "SELECT json_extract(body,'$.coverage') FROM records")]
        reasons = dict(self.db.execute('SELECT reason,COUNT(*) FROM attempts GROUP BY reason'))
        coverage = Counter(f"{r['coverage']['actual_depth']}格/{r['coverage']['groups']}时序/"
                           f"{'密集' if r['coverage']['density'] >= .3 else '疏散'}" for r in rows)
        payload = dict(name=NAME, status=status, identity=self.identity,
                       attempts=len(self.completed), accepted=len(rows), reasons=reasons,
                       progress=[dict(category=c, depth=d, accepted=self.counts[c, d], target=n, extended_input=self.extension_counts[c,d])
                                 for (c, d), n in quota.items()], coverage=dict(coverage))
        payload['density_bins'] = dict(Counter(
            '至少0.5' if r['coverage']['density'] >= .5 else
            '0.4至0.5' if r['coverage']['density'] >= .4 else
            '0.3至0.4' if r['coverage']['density'] >= .3 else '低于0.3' for r in rows))
        payload['target_bins'] = dict(Counter(
            '25至32' if r['coverage']['targets'] >= 25 else
            '17至24' if r['coverage']['targets'] >= 17 else
            '13至16' if r['coverage']['targets'] >= 13 else '3至12' for r in rows))
        payload['actual_sizes'] = dict(Counter(
            f"{min(r['coverage']['width'],r['coverage']['height'])}×"
            f"{max(r['coverage']['width'],r['coverage']['height'])}" for r in rows))
        write_json(self.directory/'progress.json', payload)
        if export_records:
            write_json(self.directory/'records.json', rows)
        return payload

    def close(self):
        try:
            self.flush()
        finally:
            self.db.close()
