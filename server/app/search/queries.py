import json


def decode_record(row):
    """只解码本次查询实际取出的 JSON 字段。"""
    item = dict(row)
    for key in ("edit", "blocks", "push", "result", "features"):
        if key in item:
            item[key] = json.loads(item[key])
    return item


def history(db, job_id, seed_id):
    return [dict(row) for row in db.execute(
        "SELECT id,hash FROM candidates WHERE job_id=? AND seed_id=? ORDER BY id", (job_id, seed_id))]


def elite(db, job_id, seed_id):
    return [decode_record(row) for row in db.execute(
        "SELECT id,blocks,push FROM candidates WHERE job_id=? AND seed_id=? AND accepted=1 "
        "ORDER BY depth,block_count,id LIMIT 8", (job_id, seed_id))]


def training_records(db, job_id):
    return [decode_record(row) for row in db.execute(
        "SELECT seed_id,result,features FROM candidates WHERE job_id=? ORDER BY id", (job_id,))]


def candidate_page(db, job_id, seed_id, accepted_only, offset, limit):
    where, args = "job_id=?", [job_id]
    if seed_id:
        where += " AND seed_id=?"
        args.append(seed_id)
    if accepted_only:
        where += " AND accepted=1"
    total = db.execute(f"SELECT COUNT(*) FROM candidates WHERE {where}", args).fetchone()[0]
    rows = db.execute(
        "SELECT id,job_id,seed_id,hash,parent_id,edit,result,accepted,improved,depth,block_count,created_at "
        f"FROM candidates WHERE {where} ORDER BY id DESC LIMIT ? OFFSET ?", [*args, limit, offset])
    return {"total": total, "items": [decode_record(row) for row in rows]}
