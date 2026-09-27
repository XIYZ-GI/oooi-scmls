from pydantic import BaseModel, Field


class TimingPushPoint(BaseModel):
    x: int = Field(ge=0, le=127, strict=True)
    y: int = Field(ge=0, le=127, strict=True)
    z: int | None = Field(default=None, ge=-129, le=-2, strict=True)


def resolve_push_point(positions, point):
    """推动点是被接触方块的位置，旧二维标注自动取所在列最后方的方块。"""
    column = [z for x, y, z in positions if x == point["x"] and y == point["y"]]
    if not column:
        raise ValueError("此位置没有可接触的移动线方块")
    rear = min(column)
    z = point.get("z")
    if z is None:
        z = rear
    if z not in column:
        raise ValueError("推动点必须对应一个移动线方块")
    if z != rear:
        raise ValueError("这个方块后方还有方块，不能作为推动点")
    return {"x": point["x"], "y": point["y"], "z": z}
