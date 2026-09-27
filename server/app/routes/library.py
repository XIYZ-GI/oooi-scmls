import asyncio
import json
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.concurrency import run_in_threadpool

from app.models.library import LibraryKind, LibraryMigration, LibraryOrder, LibraryUpdate, StoredTimingRequest
from app.repositories.library import library_repository, LibraryConflict, now
from app.services.datasets.constants import MAX_FILE_BYTES, MAX_JSON_BYTES
from app.services.datasets.parser import parse_structure
from app.services.datasets.timing import calculate_stored_timing
from app.services.label_timing import timing_executor
from app.models.load_protocol import TARGET_LOAD_BLOCKS, LOAD_TIMING_PROTOCOL


router = APIRouter(prefix="/datasets", tags=["服务器结构与标注"])
_timing_slots = asyncio.Semaphore(2)


async def limited_body(request, limit):
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > limit:
            raise HTTPException(413, "上传文件超过大小限制")
    return bytes(content)


def download(content, filename, media_type="application/json"):
    return Response(content, media_type=media_type, headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"})


@router.post("/samples/upload")
async def upload_structure(request: Request, filename: str = Query(min_length=1, max_length=300)):
    content = await limited_body(request, MAX_FILE_BYTES)
    filename = filename.replace("\\", "/").rsplit("/", 1)[-1]
    sample = await run_in_threadpool(parse_structure, content, filename)
    return await run_in_threadpool(library_repository.add, "samples", [sample], True, False, (filename, content))


@router.post("/samples/import")
async def import_dataset(request: Request):
    try:
        data = json.loads(await limited_body(request, MAX_JSON_BYTES))
    except (ValueError, UnicodeDecodeError) as error:
        raise HTTPException(422, "JSON 文件无法读取") from error
    if not isinstance(data, dict) or data.get("format") != "mcscai-labels" or data.get("version") != 1 or not isinstance(data.get("samples"), list) or len(data["samples"]) > 1000:
        raise HTTPException(422, "需要第 1 版 mcscai-labels JSON 数据集，最多 1000 个样本")
    return await run_in_threadpool(library_repository.add, "samples", data["samples"])


@router.get("/{kind}/export")
def export_library(kind: LibraryKind, sample_id: str | None = None):
    items = [library_repository.get(kind, sample_id)] if sample_id else library_repository.list(kind)
    if kind == "samples":
        data = {"format": "mcscai-labels", "version": 1, "exportedAt": now(), "samples": items,
                "coordinateConvention": {"forward": "+Z", "frontZ": -2, "targetZ": "每个目标自身的 z，旧版缺省为 0", "pushPistonZ": "pushPoint.z - 1；旧二维推动点取所在列最后方方块的 z", "observerFacing": "输出端", "sourceCoordinates": "文件内相对坐标"},
                "loadRequirement": {"blocksPerTarget": TARGET_LOAD_BLOCKS, "protocol": LOAD_TIMING_PROTOCOL, "placement": "从各目标 z 起沿 +Z 连续放置，所有目标同时加载"}}
    else:
        data = items[0] if sample_id else {"scenes": items}
    return download(json.dumps(data, ensure_ascii=False, indent=2), f"{items[0]['name'] if sample_id else '服务器数据集'}.json")


@router.post("/scenes/import")
async def import_scene(request: Request):
    try:
        data = json.loads(await limited_body(request, MAX_JSON_BYTES))
    except (ValueError, UnicodeDecodeError) as error:
        raise HTTPException(422, "JSON 结构文件无法读取") from error
    return (await run_in_threadpool(library_repository.add, "scenes", [data]))["items"][0]


@router.post("/{kind}/migrate")
def migrate_library(kind: LibraryKind, request: LibraryMigration):
    return library_repository.add(kind, request.items, migration=True)


@router.post("/{kind}/reorder")
def reorder_library(kind: LibraryKind, request: LibraryOrder):
    library_repository.reorder(kind, request.ids)
    return {"status": "ok"}


@router.get("/{kind}")
def list_library(kind: LibraryKind):
    return library_repository.list(kind)


@router.post("/scenes", status_code=201)
def create_scene(data: dict):
    return library_repository.add("scenes", [data], strict_name=True)["items"][0]


@router.get("/{kind}/{document_id}")
def get_document(kind: LibraryKind, document_id: str):
    return library_repository.get(kind, document_id)


@router.patch("/{kind}/{document_id}")
def update_document(kind: LibraryKind, document_id: str, request: LibraryUpdate):
    return library_repository.update(kind, document_id, request.revision, request.changes)


@router.delete("/{kind}/{document_id}")
def delete_document(kind: LibraryKind, document_id: str, revision: int = Query(ge=1)):
    library_repository.delete(kind, document_id, revision)
    return {"status": "ok"}


@router.post("/{kind}/{document_id}/restore")
def restore_document(kind: LibraryKind, document_id: str):
    return library_repository.restore(kind, document_id)


@router.get("/samples/{document_id}/original/{file_id}")
def original_structure(document_id: str, file_id: str):
    filename, content = library_repository.original(document_id, file_id)
    return download(content, filename, "application/octet-stream")


@router.post("/samples/{document_id}/timing")
async def compute_stored_timing(document_id: str, request: StoredTimingRequest):
    try:
        await asyncio.wait_for(_timing_slots.acquire(), timeout=0.1)
    except TimeoutError as error:
        raise HTTPException(429, "时序计算繁忙，请稍后重试") from error
    future = asyncio.get_running_loop().run_in_executor(timing_executor, calculate_stored_timing, document_id, request.revision, request.max_ticks)
    # 请求断开后计算仍由进程完成并写回数据库，槽位随实际任务完成释放。
    future.add_done_callback(lambda _: _timing_slots.release())
    return await asyncio.shield(future)


async def library_exception_handler(_request, error):
    from fastapi.responses import JSONResponse
    code = 409 if isinstance(error, LibraryConflict) else 404 if isinstance(error, KeyError) else 422
    return JSONResponse(status_code=code, content={"detail": str(error).strip("'")})
