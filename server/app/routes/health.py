from fastapi import APIRouter

router = APIRouter(tags=["运行状态"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "engine": "mcscai-engine"}

