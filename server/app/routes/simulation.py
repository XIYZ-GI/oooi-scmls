from typing import Any

from fastapi import APIRouter, HTTPException, Response

from app.models import CommandRequest, SessionCreated
from app.services import SessionNotFoundError, simulation_service

router = APIRouter(prefix="/sessions", tags=["模拟会话"])


@router.post("", response_model=SessionCreated, status_code=201)
async def create_session() -> SessionCreated:
    session_id, snapshot = await simulation_service.create()
    return SessionCreated(session_id=session_id, snapshot=snapshot)


@router.get("/{session_id}")
async def get_session(session_id: str) -> dict[str, Any]:
    try:
        return await simulation_service.snapshot(session_id)
    except SessionNotFoundError as error:
        raise HTTPException(status_code=404, detail="模拟会话不存在") from error


@router.post("/{session_id}/commands")
async def apply_command(session_id: str, request: CommandRequest) -> dict[str, Any]:
    try:
        return await simulation_service.apply(session_id, request.command)
    except SessionNotFoundError as error:
        raise HTTPException(status_code=404, detail="模拟会话不存在") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.delete("/{session_id}", status_code=204)
async def delete_session(session_id: str) -> Response:
    try:
        await simulation_service.delete(session_id)
    except SessionNotFoundError as error:
        raise HTTPException(status_code=404, detail="模拟会话不存在") from error
    return Response(status_code=204)


