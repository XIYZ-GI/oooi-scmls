"""训练前统一新旧课程的目标几何划分并冻结数据指纹。"""

from collections import Counter
import json

from ..data import read_examples
from ..serialization import digest, write_json
from ..templates import geometry_key


def reconcile(root):
    records = read_examples(root/"examples.jsonl")
    known = {}
    for row in records:
        if row["family"].startswith("legacy_"):
            key = digest(geometry_key([(t["x"], t["y"], t["z"], t["order"]) for t in row["task"]["targets"]]))
            if key in known and known[key] != row["split"]:
                raise ValueError("旧课程目标几何划分矛盾")
            known[key] = row["split"]
    for row in records:
        if row["family"] == "strong_compact":
            key = row["group"].removeprefix("strong-")
            if key in known:
                row["split"] = known[key]
    groups, tasks = {}, {}
    for row in records:
        for lookup, key in ((groups, row["group"]), (tasks, row["task_id"])):
            if key in lookup and lookup[key] != row["split"]:
                raise ValueError("来源或需求跨集合")
            lookup[key] = row["split"]
    content = "".join(json.dumps(r, ensure_ascii=False)+"\n" for r in records)
    (root/"examples.jsonl").write_text(content)
    manifest = json.loads((root/"manifest.json").read_text())
    manifest.update(examples_sha256=digest(content), by_split_family=dict(Counter(r["split"]+"/"+r["family"] for r in records)),
                    groups={s: len({r["group"] for r in records if r["split"] == s}) for s in ("train", "validation", "test")},
                    legacy_geometry_aligned=True)
    write_json(root/"manifest.json", manifest)
    return records
