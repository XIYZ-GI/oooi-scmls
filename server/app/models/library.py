from typing import Any, Literal

from pydantic import BaseModel, Field


LibraryKind = Literal["samples", "scenes"]


class LibraryUpdate(BaseModel):
    revision: int = Field(ge=1, strict=True)
    changes: dict[str, Any]


class LibraryMigration(BaseModel):
    items: list[dict[str, Any]] = Field(max_length=1000)


class LibraryOrder(BaseModel):
    ids: list[str] = Field(max_length=10000)


class StoredTimingRequest(BaseModel):
    revision: int = Field(ge=1, strict=True)
    max_ticks: int = Field(default=200, ge=8, le=2000, strict=True)
