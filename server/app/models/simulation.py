from typing import Any

from pydantic import BaseModel, Field


class CommandRequest(BaseModel):
    command: dict[str, Any] = Field(description="传递给 Rust 引擎的结构化命令")


class SessionCreated(BaseModel):
    session_id: str
    snapshot: dict[str, Any]


class ErrorMessage(BaseModel):
    detail: str

