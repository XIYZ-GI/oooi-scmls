"""需求草稿、生成任务和结果索引持久化，任务删除不影响结构库。"""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import sqlite3
import uuid

from .config import STORE, DEFAULT_TASK, DEFAULT_CANDIDATES


def now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connection():
    STORE.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(STORE/'generation.sqlite3', timeout=30)
    db.row_factory = sqlite3.Row
    try:
        with db:
            yield db
    finally:
        db.close()


def initialize():
    with connection() as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, name TEXT NOT NULL, task TEXT NOT NULL, status TEXT NOT NULL, progress INTEGER NOT NULL DEFAULT 0, message TEXT NOT NULL DEFAULT "", created_at TEXT NOT NULL, updated_at TEXT NOT NULL, deleted INTEGER NOT NULL DEFAULT 0)')
        if 'candidate_count' not in {r['name'] for r in db.execute('PRAGMA table_info(jobs)')}:
            db.execute(f'ALTER TABLE jobs ADD COLUMN candidate_count INTEGER NOT NULL DEFAULT {DEFAULT_CANDIDATES}')
        if 'model_id' not in {r['name'] for r in db.execute('PRAGMA table_info(jobs)')}:
            # 空字符串表示「跟随注册表里的默认模型」，与网页模型选择器的默认值一致。
            db.execute("ALTER TABLE jobs ADD COLUMN model_id TEXT NOT NULL DEFAULT ''")
        db.execute('CREATE TABLE IF NOT EXISTS draft (id INTEGER PRIMARY KEY, revision INTEGER NOT NULL, content TEXT NOT NULL)')
        db.execute('INSERT OR IGNORE INTO draft VALUES (1, 1, ?)', (json.dumps({'task': DEFAULT_TASK, 'group_count': 1}),))
        db.execute('UPDATE jobs SET status="error", message="服务重启，任务已中断；可重新生成" WHERE status="running"')


def decode(row):
    if row is None:
        raise KeyError('生成记录不存在')
    value = dict(row)
    value['task'] = json.loads(value['task'])
    value.setdefault('candidate_count', DEFAULT_CANDIDATES)
    return value


def list_jobs():
    with connection() as db:
        return [decode(r) for r in db.execute('SELECT * FROM jobs WHERE deleted=0 ORDER BY created_at DESC LIMIT 200')]


def get_job(job_id):
    with connection() as db:
        return decode(db.execute('SELECT * FROM jobs WHERE id=? AND deleted=0', (job_id,)).fetchone())


def create(task, name, candidate_count=DEFAULT_CANDIDATES, model_id=''):
    job_id, stamp = str(uuid.uuid4()), now()
    name = name.strip() or '生成 '+stamp[5:16].replace('T', ' ')+' · '+job_id[:4]
    with connection() as db:
        if db.execute('SELECT COUNT(*) FROM jobs WHERE deleted=0 AND status IN ("queued", "running")').fetchone()[0] >= 8:
            raise ValueError('等待生成的任务已满，请等待或取消已有任务')
        if db.execute('SELECT 1 FROM jobs WHERE deleted=0 AND name=?', (name,)).fetchone():
            raise ValueError('已有同名生成记录')
        db.execute('INSERT INTO jobs (id,name,task,status,created_at,updated_at,candidate_count,model_id) VALUES (?,?,?,"queued",?,?,?,?)',
                   (job_id, name, json.dumps(task), stamp, stamp, candidate_count, model_id))
    return get_job(job_id)


def update(job_id, **values):
    allowed = {'status', 'progress', 'message', 'name', 'deleted'}
    if not values or set(values)-allowed:
        raise ValueError('不支持的修改字段')
    with connection() as db:
        if 'name' in values and db.execute('SELECT 1 FROM jobs WHERE deleted=0 AND name=? AND id<>?', (values['name'], job_id)).fetchone():
            raise ValueError('已有同名生成记录')
        values['updated_at'] = now()
        db.execute('UPDATE jobs SET '+','.join(k+'=?' for k in values)+' WHERE id=? AND deleted=0', [*values.values(), job_id])


def draft():
    with connection() as db:
        row = db.execute('SELECT * FROM draft WHERE id=1').fetchone()
        return {'candidate_count': DEFAULT_CANDIDATES, **json.loads(row['content']), 'revision': row['revision']}


def save_draft(revision, content):
    with connection() as db:
        changed = db.execute('UPDATE draft SET content=?, revision=revision+1 WHERE id=1 AND revision=?', (json.dumps(content), revision)).rowcount
        if not changed:
            raise ValueError('需求已在其他页面修改，请刷新后再编辑')
    return {**content, 'revision': revision+1}
