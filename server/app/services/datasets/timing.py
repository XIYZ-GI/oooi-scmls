from app.models.label_timing import LabelTimingRequest
from app.repositories.library import library_repository, timing_key, LibraryConflict
from app.repositories.label_replays import LabelReplayRecorder
from app.services.label_timing import calculate_label_timing
from .coordinates import normalize_structure, annotation_error


def calculate_stored_timing(document_id, revision, max_ticks):
    sample = library_repository.get("samples", document_id)
    if sample["revision"] != revision:
        raise LibraryConflict("结构已有更新，请刷新后重新计算")
    issue = annotation_error(sample)
    if issue:
        raise ValueError(issue)
    normalized = normalize_structure(sample)
    if any(block["kind"] is None or block["layer"] != 0 for block in normalized["blocks"]):
        raise ValueError("结构含模拟器不支持的方块或附加层，点标注已保存在服务器")
    request = LabelTimingRequest(
        blocks=[{"position": block["position"], "block": {"kind": block["kind"], "facing": block["facing"]}} for block in normalized["blocks"]],
        push_point=sample["pushPoint"], targets=sample["targets"], max_ticks=max_ticks,
    )
    key = timing_key(sample)
    result = calculate_label_timing(request.model_dump(), LabelReplayRecorder(document_id, key))
    return library_repository.save_timing(document_id, key, result)
