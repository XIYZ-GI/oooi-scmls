import hashlib
import json
import sqlite3
import mcscai_engine
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

from app.services.datasets.constants import DATA_DIRECTORY
from app.services.datasets.coordinates import normalize_structure, annotation_error
from app.services.datasets.validation import validate_document
from app.models.load_protocol import TARGET_LOAD_BLOCKS, LOAD_TIMING_PROTOCOL
from app.models.push_point import resolve_push_point


class LibraryConflict(ValueError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def fingerprint(data):
    return hashlib.sha256(encoded([data.get("sourceSize"), data["blocks"]]).encode()).hexdigest()


def timing_key(data):
    targets = [{"x": point["x"], "y": point["y"], "z": point.get("z", 0)} for point in data["targets"]]
    push = data["pushPoint"]
    if push is not None:
        shape = normalize_structure(data)
        push = resolve_push_point([(block["position"]["x"], block["position"]["y"], block["position"]["z"]) for block in shape["blocks"]], push)
    return encoded([data["blocks"], data["forward"], push, targets, LOAD_TIMING_PROTOCOL, mcscai_engine.__version__])


class LibraryRepository:
    def __init__(self, path=None):
        self.path = path or DATA_DIRECTORY / "mcscai.sqlite3"

    @contextmanager
    def transaction(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY, kind TEXT NOT NULL, name TEXT NOT NULL,
                    data TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1,
                    deleted INTEGER NOT NULL DEFAULT 0, position INTEGER NOT NULL DEFAULT 0,
                    fingerprint TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS active_names ON documents(kind,name) WHERE deleted=0;
                CREATE TABLE IF NOT EXISTS originals (
                    id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id),
                    filename TEXT NOT NULL, sha256 TEXT NOT NULL, content BLOB NOT NULL,
                    UNIQUE(document_id,filename,sha256)
                );
                CREATE TABLE IF NOT EXISTS migrations (key TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id));
            """)
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def present(self, connection, row):
        value = json.loads(row["data"])
        value.update(id=row["id"], revision=row["revision"], updatedAt=row["updated_at"])
        if row["kind"] == "samples":
            value["targets"] = [{**point, "z": point.get("z", 0)} for point in value["targets"]]
            timing = value.get("timing")
            if timing and (timing.get("protocol") != LOAD_TIMING_PROTOCOL or timing.get("loadBlocks") != TARGET_LOAD_BLOCKS
                           or timing.get("engineVersion") != mcscai_engine.__version__):
                value["timing"] = None
            value["normalized"] = normalize_structure(value)
            value["annotationIssue"] = annotation_error(value)
            value["originals"] = [dict(file) for file in connection.execute("SELECT id,filename,sha256,length(content) AS size FROM originals WHERE document_id=?", (row["id"],))]
        return value

    def row(self, connection, kind, document_id, deleted=0):
        row = connection.execute("SELECT * FROM documents WHERE id=? AND kind=? AND deleted=?", (document_id, kind, deleted)).fetchone()
        if row is None:
            raise KeyError("服务器中不存在此结构")
        return row

    def list(self, kind):
        with self.transaction() as connection:
            return [self.present(connection, row) for row in connection.execute("SELECT * FROM documents WHERE kind=? AND deleted=0 ORDER BY position,id", (kind,))]

    def get(self, kind, document_id):
        with self.transaction() as connection:
            return self.present(connection, self.row(connection, kind, document_id))

    def unique_name(self, connection, kind, base):
        name = base
        suffix = 2
        while connection.execute("SELECT 1 FROM documents WHERE kind=? AND name=? AND deleted=0", (kind, name)).fetchone():
            name = f"{base[:100]}（{suffix}）"
            suffix += 1
        return name

    def add(self, kind, documents, deduplicate=False, migration=False, original=None, strict_name=False):
        validated = [validate_document(kind, value) for value in documents]
        values, added = [], 0
        with self.transaction() as connection:
            for source, data in zip(documents, validated):
                if kind == "samples" and data.get("timing"):
                    # 导入会分配新的样本编号，旧回放不能绑定到新样本。
                    data["timing"] = {k: v for k, v in data["timing"].items() if k != "replay"}
                migration_key = hashlib.sha256(encoded([kind, source.get("id"), data]).encode()).hexdigest() if migration else None
                previous = connection.execute("SELECT document_id FROM migrations WHERE key=?", (migration_key,)).fetchone() if migration else None
                digest = fingerprint(data)
                existing = connection.execute("SELECT * FROM documents WHERE kind=? AND fingerprint=? AND deleted=0 ORDER BY position LIMIT 1", (kind, digest)).fetchone() if deduplicate else None
                if previous:
                    row = connection.execute("SELECT * FROM documents WHERE id=?", (previous[0],)).fetchone()
                    if row["deleted"] == 0:
                        values.append(self.present(connection, row))
                    continue
                if existing:
                    document_id = existing["id"]
                else:
                    document_id = str(uuid4())
                    if strict_name and connection.execute("SELECT 1 FROM documents WHERE kind=? AND name=? AND deleted=0", (kind, data["name"])).fetchone():
                        raise ValueError("名称已存在")
                    data["name"] = self.unique_name(connection, kind, data["name"])
                    position = connection.execute("SELECT COALESCE(MAX(position),-1)+1 FROM documents WHERE kind=?", (kind,)).fetchone()[0]
                    connection.execute("INSERT INTO documents(id,kind,name,data,position,fingerprint,updated_at) VALUES(?,?,?,?,?,?,?)", (document_id, kind, data["name"], encoded(data), position, digest, now()))
                    added += 1
                if original:
                    filename, content = original
                    connection.execute("INSERT OR IGNORE INTO originals VALUES(?,?,?,?,?)", (str(uuid4()), document_id, filename, hashlib.sha256(content).hexdigest(), content))
                if migration_key:
                    connection.execute("INSERT INTO migrations VALUES(?,?)", (migration_key, document_id))
                values.append(self.present(connection, self.row(connection, kind, document_id)))
        return {"items": values, "added": added}

    def update(self, kind, document_id, revision, changes):
        allowed = {"name", "blocks"} if kind == "scenes" else {"name", "forward", "pushPoint", "targets", "author", "notes", "completed"}
        if set(changes) - allowed:
            raise ValueError("请求包含不可编辑字段")
        with self.transaction() as connection:
            row = self.row(connection, kind, document_id)
            if row["revision"] != revision:
                raise LibraryConflict("此结构已在另一页面修改。请重新读取服务器版本后再编辑，当前修改未覆盖服务器。")
            data = json.loads(row["data"])
            if kind == "samples" and set(changes) & {"forward", "pushPoint", "targets"}:
                data["timing"] = None
            data = validate_document(kind, {**data, **changes})
            try:
                connection.execute("UPDATE documents SET data=?,name=?,revision=revision+1,updated_at=?,fingerprint=? WHERE id=?", (encoded(data), data["name"], now(), fingerprint(data), document_id))
            except sqlite3.IntegrityError as error:
                raise ValueError("名称已存在") from error
            return self.present(connection, self.row(connection, kind, document_id))

    def delete(self, kind, document_id, revision):
        with self.transaction() as connection:
            row = self.row(connection, kind, document_id)
            if row["revision"] != revision:
                raise LibraryConflict("此结构已有更新，请刷新后再删除")
            connection.execute("UPDATE documents SET deleted=1,revision=revision+1,updated_at=? WHERE id=?", (now(), document_id))

    def restore(self, kind, document_id):
        with self.transaction() as connection:
            row = self.row(connection, kind, document_id, deleted=1)
            data = json.loads(row["data"])
            data["name"] = self.unique_name(connection, kind, data["name"])
            connection.execute("UPDATE documents SET deleted=0,name=?,data=?,revision=revision+1,updated_at=? WHERE id=?", (data["name"], encoded(data), now(), document_id))
            return self.present(connection, self.row(connection, kind, document_id))

    def reorder(self, kind, ids):
        with self.transaction() as connection:
            current = [row[0] for row in connection.execute("SELECT id FROM documents WHERE kind=? AND deleted=0 ORDER BY position,id", (kind,))]
            if len(ids) != len(set(ids)) or set(ids) != set(current):
                raise LibraryConflict("结构列表已有变化，请刷新后重新排序")
            for index, document_id in enumerate(ids):
                connection.execute("UPDATE documents SET position=? WHERE id=?", (index, document_id))

    def original(self, document_id, file_id):
        with self.transaction() as connection:
            self.row(connection, "samples", document_id)
            row = connection.execute("SELECT filename,content FROM originals WHERE id=? AND document_id=?", (file_id, document_id)).fetchone()
            if row is None:
                raise KeyError("原始文件不存在；从旧浏览器迁移的样本可能没有原始二进制文件")
            return row["filename"], row["content"]

    def save_timing(self, document_id, key, result):
        with self.transaction() as connection:
            row = self.row(connection, "samples", document_id)
            data = json.loads(row["data"])
            if timing_key(data) != key:
                raise LibraryConflict("点标注已更新，本次时序结果已丢弃")
            data["timing"] = {**result, "computedAt": now()}
            connection.execute("UPDATE documents SET data=?,updated_at=? WHERE id=?", (encoded(data), now(), document_id))
            return self.present(connection, self.row(connection, "samples", document_id))


library_repository = LibraryRepository()
