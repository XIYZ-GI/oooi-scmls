import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException

from app.models.label_timing import LabelTimingRequest
from app.services.label_timing import calculate_label_timing, timing_executor


router = APIRouter(prefix="/labels", tags=["移动线标注"])
_slots = asyncio.Semaphore(2)


@router.post("/timing")
async def compute_timing(request: LabelTimingRequest) -> dict[str, Any]:
    try:
        await asyncio.wait_for(_slots.acquire(), timeout=0.1)
    except TimeoutError as error:
        raise HTTPException(status_code=429, detail="时序计算繁忙，请稍后重试") from error
    try:
        return await asyncio.get_running_loop().run_in_executor(
            timing_executor, calculate_label_timing, request.model_dump(),
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=f"模拟器计算失败：{error}") from error
    finally:
        _slots.release()
