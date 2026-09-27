import json
import sqlite3
from contextlib import contextmanager
from uuid import uuid4

from app.repositories.library import encoded, now
from app.services.datasets.constants import DATA_DIRECTORY
from . import queries


class SearchRepository:
    @contextmanager
    def connection(self):
        DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(DATA_DIRECTORY / "search.sqlite3", timeout=15)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, state TEXT NOT NULL,
                    config TEXT NOT NULL, seeds TEXT NOT NULL, model TEXT,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, error TEXT NOT NULL DEFAULT ''
                );
                CREATE UNIQUE INDEX IF NOT EXISTS job_names ON jobs(name) WHERE state!='deleted';
                CREATE TABLE IF NOT EXISTS candidates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL, seed_id TEXT NOT NULL,
                    hash TEXT NOT NULL, parent_id INTEGER, edit TEXT NOT NULL, blocks TEXT NOT NULL,
                    push TEXT NOT NULL, result TEXT NOT NULL, features TEXT NOT NULL,
                    accepted INTEGER NOT NULL, improved INTEGER NOT NULL, depth INTEGER NOT NULL,
                    block_count INTEGER NOT NULL, created_at TEXT NOT NULL,
                    UNIQUE(job_id, seed_id, hash)
                );
                CREATE INDEX IF NOT EXISTS candidate_jobs ON candidates(job_id, seed_id);
            """)
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def get(self, job_id):
        with self.connection() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                raise KeyError("搜索任务不存在")
            job = dict(row)
            for key in ("config", "seeds", "model"):
                job[key] = json.loads(job[key]) if job[key] else None
            return job

    def stats(self, job_id):
        with self.connection() as db:
            return [dict(row) for row in db.execute(
                "SELECT seed_id,COUNT(*) AS attempted,SUM(accepted) AS accepted,SUM(improved) AS improved "
                "FROM candidates WHERE job_id=? GROUP BY seed_id", (job_id,))]

    def present(self, job):
        stats = {s["seed_id"]: s for s in self.stats(job["id"])}
        return {**{k: v for k, v in job.items() if k not in ("seeds", "model")},
                "model": None if not job["model"] else {k: v for k, v in job["model"].items() if k != "weights"},
                "seeds": [{**{k: s[k] for k in ("id", "name", "revision", "width", "height", "depth", "group", "split")},
                           "blocks": len(s["request"]["blocks"]), "targets": len(s["request"]["targets"]),
                           **stats.get(s["id"], {"attempted": 0, "accepted": 0, "improved": 0})} for s in job["seeds"]]}

    def list(self):
        with self.connection() as db:
            ids = [row[0] for row in db.execute("SELECT id FROM jobs WHERE state!='deleted' ORDER BY created_at DESC")]
        return [self.present(self.get(job_id)) for job_id in ids]

    def create(self, name, config, seeds):
        job_id = str(uuid4())
        with self.connection() as db:
            if db.execute("SELECT 1 FROM jobs WHERE name=? AND state!='deleted'", (name,)).fetchone():
                raise ValueError("任务名称已存在")
            db.execute("INSERT INTO jobs(id,name,state,config,seeds,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                       (job_id, name, "queued", encoded(config), encoded(seeds), now(), now()))
        return self.present(self.get(job_id))

    def update(self, job_id, *, state=None, name=None, budget=None, error=None, model=None):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                raise KeyError("搜索任务不存在")
            if name is not None:
                if db.execute("SELECT 1 FROM jobs WHERE name=? AND id!=? AND state!='deleted'", (name, job_id)).fetchone():
                    raise ValueError("任务名称已存在")
                db.execute("UPDATE jobs SET name=? WHERE id=?", (name, job_id))
            if budget is not None:
                if row["state"] in ("running", "queued"):
                    raise ValueError("先暂停任务，再修改候选预算")
                config = json.loads(row["config"])
                config["per_seed"] = budget
                db.execute("UPDATE jobs SET config=? WHERE id=?", (encoded(config), job_id))
            if state is not None:
                db.execute("UPDATE jobs SET state=? WHERE id=?", (state, job_id))
            if error is not None:
                db.execute("UPDATE jobs SET error=? WHERE id=?", (error, job_id))
            if model is not None:
                db.execute("UPDATE jobs SET model=? WHERE id=?", (encoded(model), job_id))
            db.execute("UPDATE jobs SET updated_at=? WHERE id=?", (now(), job_id))

    def claim(self):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT id FROM jobs WHERE state IN ('running','queued') ORDER BY created_at LIMIT 1").fetchone()
            if row:
                db.execute("UPDATE jobs SET state='running',updated_at=? WHERE id=?", (now(), row[0]))
                return row[0]
        return None

    def finish(self, job_id):
        with self.connection() as db:
            db.execute("UPDATE jobs SET state='completed',updated_at=? WHERE id=? AND state='running'", (now(), job_id))

    def records(self, job_id, seed_id=None):
        with self.connection() as db:
            query = "SELECT * FROM candidates WHERE job_id=?"
            args = [job_id]
            if seed_id:
                query += " AND seed_id=?"
                args.append(seed_id)
            rows = db.execute(query + " ORDER BY id", args).fetchall()
        records = []
        for row in rows:
            item = dict(row)
            for key in ("edit", "blocks", "push", "result", "features"):
                item[key] = json.loads(item[key])
            records.append(item)
        return records

    def search_inputs(self, job_id, seed_id):
        with self.connection() as db:
            return queries.history(db, job_id, seed_id), queries.elite(db, job_id, seed_id)

    def training_records(self, job_id):
        with self.connection() as db:
            return queries.training_records(db, job_id)

    def candidate_page(self, job_id, seed_id, accepted_only, offset, limit):
        with self.connection() as db:
            return queries.candidate_page(db, job_id, seed_id, accepted_only, offset, limit)

    def candidate(self, job_id, candidate_id):
        with self.connection() as db:
            row = db.execute("SELECT * FROM candidates WHERE job_id=? AND id=?", (job_id, candidate_id)).fetchone()
            if row is None:
                raise KeyError("候选结构不存在")
            return queries.decode_record(row)

    def save(self, job_id, seed_id, proposal, result, features, improved):
        zs = [b["position"]["z"] for b in proposal["blocks"]]
        with self.connection() as db:
            # 暂停时允许保存已计算的一项，删除与取消则丢弃在途结果。
            state = db.execute("SELECT state FROM jobs WHERE id=?", (job_id,)).fetchone()[0]
            if state in ("deleted", "cancelled"):
                return
            db.execute("INSERT OR IGNORE INTO candidates(job_id,seed_id,hash,parent_id,edit,blocks,push,result,features,accepted,improved,depth,block_count,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       (job_id, seed_id, proposal["hash"], proposal.get("parent_id"), encoded(proposal["edit"]),
                        encoded(proposal["blocks"]), encoded(proposal["push"]), encoded(result), encoded(features),
                        int(result["accepted"]), int(improved), max(zs) - min(zs) + 1, len(zs), now()))
            db.execute("UPDATE jobs SET updated_at=? WHERE id=?", (now(), job_id))


search_repository = SearchRepository()
