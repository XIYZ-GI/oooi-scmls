import asyncio
import json
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from fastapi import WebSocket
from mcscai_engine import Simulator


@dataclass
class SimulationSession:
    engine: Simulator = field(default_factory=Simulator)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    subscribers: set[WebSocket] = field(default_factory=set)


class SessionNotFoundError(KeyError):
    pass


class SimulationService:
    def __init__(self) -> None:
        self._sessions: dict[str, SimulationSession] = {}
        self._sessions_lock = asyncio.Lock()

    async def create(self) -> tuple[str, dict[str, Any]]:
        session_id = str(uuid4())
        session = SimulationSession()
        async with self._sessions_lock:
            self._sessions[session_id] = session
        return session_id, self._decode_snapshot(session.engine.snapshot())

    async def delete(self, session_id: str) -> None:
        async with self._sessions_lock:
            session = self._sessions.pop(session_id, None)
        if session is None:
            raise SessionNotFoundError(session_id)
        for websocket in tuple(session.subscribers):
            await websocket.close(code=1001, reason="模拟会话已删除")

    async def snapshot(self, session_id: str) -> dict[str, Any]:
        session = self._get(session_id)
        async with session.lock:
            return self._decode_snapshot(session.engine.snapshot())

    async def apply(
        self, session_id: str, command: dict[str, Any]
    ) -> dict[str, Any]:
        session = self._get(session_id)
        async with session.lock:
            snapshot = self._decode_snapshot(
                session.engine.apply(
                    json.dumps(command, ensure_ascii=False, separators=(",", ":"))
                )
            )
        await self._broadcast(session, {"type": "snapshot", "snapshot": snapshot})
        return snapshot

    async def subscribe(self, session_id: str, websocket: WebSocket) -> None:
        session = self._get(session_id)
        await websocket.accept()
        session.subscribers.add(websocket)
        await websocket.send_json(
            {"type": "snapshot", "snapshot": await self.snapshot(session_id)}
        )

    def unsubscribe(self, session_id: str, websocket: WebSocket) -> None:
        session = self._sessions.get(session_id)
        if session is not None:
            session.subscribers.discard(websocket)

    def _get(self, session_id: str) -> SimulationSession:
        try:
            return self._sessions[session_id]
        except KeyError as error:
            raise SessionNotFoundError(session_id) from error

    async def _broadcast(
        self, session: SimulationSession, payload: dict[str, Any]
    ) -> None:
        stale: list[WebSocket] = []
        for websocket in tuple(session.subscribers):
            try:
                await websocket.send_json(payload)
            except RuntimeError:
                stale.append(websocket)
        for websocket in stale:
            session.subscribers.discard(websocket)

    @staticmethod
    def _decode_snapshot(snapshot: str) -> dict[str, Any]:
        return json.loads(snapshot)


simulation_service = SimulationService()

