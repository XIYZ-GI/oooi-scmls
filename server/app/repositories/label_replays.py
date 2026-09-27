"""分块压缩保存打标模拟的真实快照，浏览器按需读取。"""

import gzip
import hashlib
import json
from uuid import uuid4, UUID

from app.services.datasets.constants import DATA_DIRECTORY

CHUNK_SIZE = 24
REPLAY_DIRECTORY = DATA_DIRECTORY / "label-replays"


def replay_directory(run_id):
    try:
        name = str(UUID(run_id))
    except (ValueError, TypeError, AttributeError) as error:
        raise ValueError("回放编号无效") from error
    return REPLAY_DIRECTORY / name


class LabelReplayRecorder:
    def __init__(self, sample_id, key):
        self.id = str(uuid4())
        self.path = replay_directory(self.id)
        self.path.mkdir(parents=True)
        self.sample_id = sample_id
        self.key = hashlib.sha256(key.encode()).hexdigest()
        self.frames = []
        self.count = 0
        self.last_sequence = 0
        self.members = []

    def append(self, snapshot, tracker):
        frame = {k: v for k, v in snapshot.items() if k != "events"}
        frame["events"] = [e for e in snapshot["events"] if e["sequence"] > self.last_sequence]
        self.last_sequence = max((e["sequence"] for e in snapshot["events"]), default=self.last_sequence)
        self.frames.append({"snapshot": frame, "targets": [dict(p) for p in tracker.results]})
        self.members = tracker.members
        self.count += 1
        if len(self.frames) == CHUNK_SIZE:
            self.flush()

    def flush(self):
        if not self.frames:
            return
        start = self.count - len(self.frames)
        with gzip.open(self.path / f"{start // CHUNK_SIZE}.json.gz", "wt", encoding="utf-8", compresslevel=1) as handle:
            handle.write(json.dumps({"start": start, "frames": self.frames}, ensure_ascii=False, separators=(",", ":")))
        self.frames.clear()

    def finish(self, result):
        self.flush()
        value = {"id": self.id, "sampleId": self.sample_id, "inputKey": self.key,
                 "frameCount": self.count, "chunkSize": CHUNK_SIZE, "result": result,
                 "targets": [{**p, "blockIds": [i for i, _ in members]}
                             for p, members in zip(result["targets"], self.members)]}
        (self.path / "manifest.json").write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return {"id": self.id, "frameCount": self.count}


def read_manifest(run_id):
    path = replay_directory(run_id) / "manifest.json"
    if not path.exists():
        raise KeyError("回放尚未生成或不存在，请重新运行")
    return json.loads(path.read_text(encoding="utf-8"))
