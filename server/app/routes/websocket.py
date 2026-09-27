from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services import SessionNotFoundError, simulation_service

router = APIRouter(prefix="/sessions", tags=["模拟事件流"])


@router.websocket("/{session_id}/stream")
async def session_stream(websocket: WebSocket, session_id: str) -> None:
    try:
        await simulation_service.subscribe(session_id, websocket)
    except SessionNotFoundError:
        await websocket.close(code=4404, reason="模拟会话不存在")
        return
    try:
        while True:
            message = await websocket.receive_json()
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        simulation_service.unsubscribe(session_id, websocket)

