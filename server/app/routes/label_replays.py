"""打标回放只读取服务器实际计算结果，标注变更后禁止使用旧轨迹。"""

import hashlib

from fastapi import APIRouter, Path
from fastapi.responses import FileResponse

from app.repositories.library import library_repository, timing_key, LibraryConflict
from app.repositories.label_replays import read_manifest, replay_directory

router = APIRouter(prefix="/datasets/samples", tags=["打标运行回放"])


def current_manifest(document_id, run_id):
    sample = library_repository.get("samples", document_id)
    value = read_manifest(run_id)
    key = hashlib.sha256(timing_key(sample).encode()).hexdigest()
    if value["sampleId"] != document_id or value["inputKey"] != key:
        raise LibraryConflict("结构或点标注已改变，请重新运行")
    return value


@router.get("/{document_id}/replays/{run_id}")
def replay_info(document_id: str, run_id: str):
    value = current_manifest(document_id, run_id)
    return {k: v for k, v in value.items() if k != "inputKey"}


@router.get("/{document_id}/replays/{run_id}/chunks/{chunk}")
def replay_chunk(document_id: str, run_id: str, chunk: int = Path(ge=0)):
    value = current_manifest(document_id, run_id)
    if chunk * value["chunkSize"] >= value["frameCount"]:
        raise ValueError("回放刻超出范围")
    return FileResponse(replay_directory(run_id) / f"{chunk}.json.gz", media_type="application/json",
                        headers={"Content-Encoding": "gzip", "Cache-Control": "no-store"})
