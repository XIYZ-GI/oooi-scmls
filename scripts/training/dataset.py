"""把数据合成器产出的记录冻结成训练集与实验清单。

数据合成器的产物形态不统一：批量构造存 SQLite（``records`` 表的 ``body`` 列），
早期导出存逐行 JSON 或 gzip 压缩的 JSONL。这里统一读成「需求 + 结构 + 推动点」
三件套，写出一份不可变的 ``dataset.jsonl`` 与 ``manifest.json``。

清单里记录数据指纹，训练入口据此校验断点身份：换了数据就不能续训。
"""

import argparse
import gzip
import hashlib
import json
import sqlite3
from pathlib import Path

from training.serialization import encode_structure
from training.serialization import digest as _digest


def read_records(path):
    """读一份合成器产出：``.sqlite3`` 读 records 表，``.jsonl[.gz]`` 逐行读。"""
    path = Path(path)
    if path.suffix == ".sqlite3":
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
            return [json.loads(body) for (body,) in db.execute("SELECT body FROM records ORDER BY id")]
    handle = gzip.open(path, "rt", encoding="utf-8") if path.suffix == ".gz" else path.open(encoding="utf-8")
    with handle:
        return [json.loads(line) for line in handle if line.strip()]


def normalize(row, index):
    """只保留模型需要的字段；结构必须先通过引擎的编码检查。"""
    encode_structure(row["task"], **row["proposal"])
    return dict(id=row.get("id") or f"record-{index:07d}", split="train",
                task=row["task"], proposal=row["proposal"])


def sha256(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def build(output, sources, name, limit=0, note=""):
    """把若干合成器产出合成一个实验数据集。

    ``sources`` 里的顺序就是样本顺序；``limit`` 只用于快速冒烟，正式训练不要传。
    多份产出之间可能有同编号的记录（同一批数据的不同导出），按编号去重并保留先出现的。
    """
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    dataset = output / "dataset.jsonl"
    if dataset.exists():
        raise SystemExit(f"已存在冻结数据集：{dataset}；如需重做请先移走旧文件")
    rows, seen, hasher = [], set(), hashlib.sha256()
    for source in sources:
        for row in read_records(source):
            record = normalize(row, len(rows))
            if record["id"] in seen:
                continue
            seen.add(record["id"])
            rows.append(record)
            if limit and len(rows) >= limit:
                break
        if limit and len(rows) >= limit:
            break
    with dataset.open("w", encoding="utf-8") as handle:
        for record in rows:
            text = json.dumps(record, ensure_ascii=False) + "\n"
            handle.write(text)
            hasher.update(text.encode())
    manifest = dict(experiment=name, training_records=len(rows), holdout_records=0,
                    sources=[str(source) for source in sources],
                    source_files={str(source): sha256(source) for source in sources},
                    dataset_sha256=hasher.hexdigest(), note=note,
                    split_policy="全部记录进入训练；两个发布模型都没有划分内部验证集",
                    selection="正式评估统一使用训练结束时的最终检查点")
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"训练记录": len(rows), "数据指纹": _digest(rows)[:16]}, ensure_ascii=False), flush=True)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="实验目录，例如 data/generation/my-experiment")
    parser.add_argument("--name", required=True, help="实验名称，写进清单")
    parser.add_argument("--source", action="append", required=True,
                        help="合成器产出：records.sqlite3 或 *.jsonl / *.jsonl.gz；可重复")
    parser.add_argument("--limit", type=int, default=0, help="只保留前 N 条，供冒烟使用")
    parser.add_argument("--note", default="")
    args = parser.parse_args()
    build(args.output, [Path(source) for source in args.source], args.name, args.limit, args.note)


if __name__ == "__main__":
    main()
