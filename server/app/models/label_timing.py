from typing import Literal

from pydantic import BaseModel, Field, model_validator
from .load_protocol import MIN_TARGET_Z, MAX_TARGET_Z
from .push_point import TimingPushPoint, resolve_push_point


class TimingPosition(BaseModel):
    x: int = Field(ge=0, le=127, strict=True)
    y: int = Field(ge=0, le=127, strict=True)
    z: int = Field(ge=-129, le=-2, strict=True)


class TimingPoint(BaseModel):
    x: int = Field(ge=0, le=127, strict=True)
    y: int = Field(ge=0, le=127, strict=True)


class TimingTarget(TimingPoint):
    z: int = Field(default=0, ge=MIN_TARGET_Z, le=MAX_TARGET_Z, strict=True)


class TimingBlockSpec(BaseModel):
    kind: Literal[
        "slime_block", "honey_block", "piston", "sticky_piston", "redstone_block",
        "observer", "iron_block", "light_blue_glazed_terracotta", "glass",
    ]
    facing: Literal[
        "positive_x", "negative_x", "positive_y", "negative_y", "positive_z", "negative_z",
    ]


class TimingBlock(BaseModel):
    position: TimingPosition
    block: TimingBlockSpec


class LabelTimingRequest(BaseModel):
    blocks: list[TimingBlock] = Field(min_length=1, max_length=4096)
    push_point: TimingPushPoint
    targets: list[TimingTarget] = Field(min_length=1, max_length=4096)
    max_ticks: int = Field(default=200, ge=8, le=2000, strict=True)

    @model_validator(mode="after")
    def validate_layout(self) -> "LabelTimingRequest":
        positions = {(item.position.x, item.position.y, item.position.z) for item in self.blocks}
        if len(positions) != len(self.blocks):
            raise ValueError("结构中存在重复坐标")
        if max(position[2] for position in positions) != -2:
            raise ValueError("移动线最前面必须对齐 z = -2")
        self.push_point.z = resolve_push_point(positions, self.push_point.model_dump())["z"]
        targets = {(point.x, point.y) for point in self.targets}
        if len(targets) != len(self.targets):
            raise ValueError("目标点坐标不能重复")
        max_x = max(position[0] for position in positions)
        max_y = max(position[1] for position in positions)
        if any(x > max_x or y > max_y for x, y in targets):
            raise ValueError("目标点必须位于移动线截面范围内")
        for point in self.targets:
            if any(x == point.x and y == point.y and z >= point.z for x, y, z in positions):
                raise ValueError(f"目标 ({point.x}, {point.y}) 的负载必须放在这一列移动线方块的前方")
        return self
