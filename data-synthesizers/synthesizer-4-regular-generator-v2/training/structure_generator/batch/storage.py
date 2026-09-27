"""SQLite断点、跨专项几何去重与有界内存保存。"""

import json
import sqlite3
from datetime import datetime, timezone

from .profiles import admission
from .reporting import dimensions


class Store:
    def __init__(self, directory, identity, profiles, skeleton_limit=16):
        # 配额里的尺寸与机制可用元组声明，断点JSON读回为列表；统一后比较身份。
        identity = json.loads(json.dumps(identity, ensure_ascii=False))
        self.directory, self.profiles = directory, profiles
        self.by_id = {p['id']: p for p in profiles}
        self.source_digest = identity.get('source_digest', '')
        self.skeleton_limit = skeleton_limit
        directory.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(directory / 'records.sqlite3')
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS pending (id INTEGER PRIMARY KEY, profile TEXT, job TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS records (
                id TEXT PRIMARY KEY, signature TEXT UNIQUE, profile TEXT,
                category TEXT, depth INTEGER, skeleton TEXT, body TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS records_skeleton ON records(skeleton);
            CREATE INDEX IF NOT EXISTS records_profile ON records(profile);
            CREATE TABLE IF NOT EXISTS stats (
                profile TEXT PRIMARY KEY, accepted INTEGER DEFAULT 0,
                attempts INTEGER DEFAULT 0, cpu_seconds REAL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS reasons (
                profile TEXT, reason TEXT, count INTEGER, PRIMARY KEY(profile,reason));
            CREATE TABLE IF NOT EXISTS coverage (
                dimension TEXT, value TEXT, count INTEGER, PRIMARY KEY(dimension,value));
            CREATE TABLE IF NOT EXISTS errors (
                id INTEGER PRIMARY KEY, profile TEXT, source_digest TEXT,
                created_at TEXT, body TEXT NOT NULL);
        ''')
        saved = self.db.execute("SELECT body FROM metadata WHERE key='identity'").fetchone()
        if saved and json.loads(saved[0]) != identity:
            self.db.close()
            raise ValueError('源码、引擎或采样方案与断点不符；请使用新目录或恢复原源码')
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO metadata VALUES ('identity',?)",
                            (json.dumps(identity, ensure_ascii=False),))
            self.db.execute("INSERT OR IGNORE INTO metadata VALUES ('next_index','0')")
            self.db.execute("INSERT OR IGNORE INTO metadata VALUES ('consecutive_errors','0')")
            self.db.executemany('INSERT OR IGNORE INTO stats(profile) VALUES (?)',
                                [(p['id'],) for p in profiles])

    def stats(self):
        return {p: dict(accepted=a, attempts=n, cpu_seconds=t) for p, a, n, t in
                self.db.execute('SELECT profile,accepted,attempts,cpu_seconds FROM stats')}

    def reserve(self, profile, make_job):
        index = int(self.db.execute("SELECT body FROM metadata WHERE key='next_index'").fetchone()[0])
        job = make_job(index)
        self.db.execute('INSERT INTO pending VALUES (?,?,?)',
                        (index, profile, json.dumps(job, ensure_ascii=False)))
        self.db.execute("UPDATE metadata SET body=? WHERE key='next_index'", (str(index + 1),))
        return job

    def pending(self):
        return [(p, json.loads(j)) for p, j in self.db.execute('SELECT profile,job FROM pending ORDER BY id')]

    def finish(self, profile_id, result):
        profile = self.by_id[profile_id]
        exists = self.db.execute('SELECT profile,job FROM pending WHERE id=?', (result['index'],)).fetchone()
        if not exists or exists[0] != profile_id:
            raise ValueError('结果不属于当前待处理任务，拒绝重复统计')
        reason, row, accepted = result['reason'], result.get('row'), 0
        error = result.get('error')
        if error:
            if row is not None or list(error['job']) != json.loads(exists[1]):
                raise ValueError('隔离的异常不能包含训练样本，且必须对应原任务')
            reason = '候选执行异常，已隔离'
            self.db.execute('INSERT INTO errors VALUES (?,?,?,?,?)',
                            (result['index'], profile_id, self.source_digest,
                             datetime.now(timezone.utc).isoformat(), json.dumps(error, ensure_ascii=False)))
        consecutive = self.consecutive_errors() + 1 if error else 0
        self.db.execute("UPDATE metadata SET body=? WHERE key='consecutive_errors'", (str(consecutive),))
        if row:
            reason = admission(row, profile)
            count = self.db.execute('SELECT accepted FROM stats WHERE profile=?', (profile_id,)).fetchone()[0]
            if not reason and count >= profile['quota']:
                reason = '专项配额已满'
            if not reason and self.db.execute('SELECT 1 FROM records WHERE signature=?',
                                             (row['canonical'],)).fetchone():
                reason = '对称或材料互换等价结构重复'
            if not reason and self.db.execute('SELECT COUNT(*) FROM records WHERE skeleton=?',
                                             (row['skeleton'],)).fetchone()[0] >= self.skeleton_limit:
                reason = '相同骨架变体达到上限'
            if not reason:
                row['batch_profile'] = profile_id
                self.db.execute('INSERT INTO records VALUES (?,?,?,?,?,?,?)',
                    (row['id'], row['canonical'], profile_id, row['family'], row['coverage']['actual_depth'],
                     row['skeleton'], json.dumps(row, ensure_ascii=False, separators=(',', ':'))))
                for dimension, value in dimensions(row):
                    self.db.execute('''INSERT INTO coverage VALUES (?,?,1)
                        ON CONFLICT(dimension,value) DO UPDATE SET count=count+1''', (dimension, value))
                accepted, reason = 1, '已保存'
        self.db.execute('UPDATE stats SET accepted=accepted+?,attempts=attempts+1,cpu_seconds=cpu_seconds+? WHERE profile=?',
                        (accepted, result['worker_cpu_seconds'], profile_id))
        self.db.execute('''INSERT INTO reasons VALUES (?,?,1)
            ON CONFLICT(profile,reason) DO UPDATE SET count=count+1''', (profile_id, reason))
        self.db.execute('DELETE FROM pending WHERE id=?', (result['index'],))
        return reason

    def consecutive_errors(self):
        return int(self.db.execute("SELECT body FROM metadata WHERE key='consecutive_errors'").fetchone()[0])

    def close(self):
        self.db.close()
