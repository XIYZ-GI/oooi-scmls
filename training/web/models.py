"""网页输入限制与草稿校验。"""

from pydantic import BaseModel, Field, model_validator
from .config import DEFAULT_CANDIDATES, MAX_CANDIDATES


class Target(BaseModel):
    x: int = Field(ge=0, le=14, strict=True)
    y: int = Field(ge=0, le=14, strict=True)
    # 目标点 z 表示该列第一块负载沿前进方向的起始位置，现实中由使用者摆放决定，不限定为 0。
    z: int = Field(default=0, ge=-12, le=8, strict=True)
    order: int = Field(ge=1, le=32, strict=True)


class Board(BaseModel):
    width: int = Field(default=7, ge=1, le=15, strict=True)
    height: int = Field(default=5, ge=1, le=15, strict=True)
    depth: int = Field(default=2, ge=2, le=9, strict=True)
    targets: list[Target] = Field(default_factory=list, max_length=32)
    # 0 表示无时限：不读每轮刻数的版本按“推完即结束”判定。
    max_ticks: int = Field(default=48, ge=0, le=200, strict=True)
    rounds: int = Field(default=3, ge=2, le=10, strict=True)
    load_blocks: int = Field(default=10, ge=10, le=10, strict=True)

    @model_validator(mode='after')
    def check(self):
        if self.width*self.height*self.depth > 512:
            raise ValueError('宽×高×厚度最多512格')
        if any(t.x >= self.width or t.y >= self.height for t in self.targets):
            raise ValueError('目标点超出网格')
        if len({(t.x, t.y) for t in self.targets}) != len(self.targets):
            raise ValueError('同一格不能重复标注')
        return self


class Draft(BaseModel):
    model_id: str | None = Field(default=None, max_length=100)
    task: Board
    candidate_count: int = Field(default=DEFAULT_CANDIDATES, ge=1, le=MAX_CANDIDATES, strict=True)
    group_count: int = Field(ge=1, le=32, strict=True)
    revision: int = Field(ge=1, strict=True)


class CreateJob(BaseModel):
    model_id: str | None = Field(default=None, max_length=100)
    task: Board
    candidate_count: int = Field(default=DEFAULT_CANDIDATES, ge=1, le=MAX_CANDIDATES, strict=True)
    name: str = Field(default='', max_length=100)


class Rename(BaseModel):
    name: str = Field(min_length=1, max_length=100)
