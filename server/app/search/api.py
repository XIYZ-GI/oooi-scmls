import io
import json
import math
import zipfile
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from app.repositories.library import encoded
from app.routes.library import download
from .learning import fit_model
from .mutations import FEATURE_NAMES
from .repository import search_repository as repository
from .seeds import freeze_seeds, digest


router = APIRouter(prefix="/search", tags=["搜索与训练"])


class CreateJob(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    per_seed: int = Field(default=32, ge=1, le=10000, strict=True)
    rounds: int = Field(default=3, ge=2, le=20, strict=True)
    random_seed: int = Field(default=20260920, ge=0, le=2**31 - 1, strict=True)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        if not value.strip():
            raise ValueError("任务名称不能为空")
        return value.strip()


class UpdateJob(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    per_seed: int | None = Field(default=None, ge=1, le=10000, strict=True)
    action: Literal["pause", "resume", "cancel"] | None = None


def active_job(job_id):
    job = repository.get(job_id)
    if job["state"] == "deleted":
        raise KeyError("搜索任务已删除")
    return job


@router.get("/jobs")
def list_jobs():
    return repository.list()


@router.post("/jobs", status_code=201)
def create_job(request: CreateJob):
    return repository.create(request.name, request.model_dump(exclude={"name"}), freeze_seeds())


@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    return repository.present(active_job(job_id))


@router.patch("/jobs/{job_id}")
def update_job(job_id: str, request: UpdateJob):
    active_job(job_id)
    name = request.name.strip() if request.name is not None else None
    if name == "":
        raise ValueError("任务名称不能为空")
    states = {"pause": "paused", "resume": "queued", "cancel": "cancelled"}
    repository.update(job_id, name=name, budget=request.per_seed,
                      state=states.get(request.action), error="" if request.action == "resume" else None)
    return get_job(job_id)


@router.delete("/jobs/{job_id}")
def delete_job(job_id: str):
    active_job(job_id)
    repository.update(job_id, state="deleted")
    return {"status": "ok"}


@router.post("/jobs/{job_id}/restore")
def restore_job(job_id: str):
    job = repository.get(job_id)
    if job["state"] != "deleted":
        raise ValueError("任务没有被删除")
    if any(j["name"] == job["name"] for j in repository.list()):
        raise ValueError("已有同名任务，请先给该任务改名")
    repository.update(job_id, state="paused")
    return get_job(job_id)


@router.get("/jobs/{job_id}/candidates")
def candidates(job_id: str, seed_id: str | None = None, accepted_only: bool = False,
               offset: int = Query(default=0, ge=0), limit: int = Query(default=50, ge=1, le=100)):
    active_job(job_id)
    return repository.candidate_page(job_id, seed_id, accepted_only, offset, limit)


def candidate_detail(job_id, candidate_id):
    job = active_job(job_id)
    candidate = repository.candidate(job_id, candidate_id)
    seed = next(s for s in job["seeds"] if s["id"] == candidate["seed_id"])
    return {"candidate": candidate, "seed": {k: v for k, v in seed.items() if k != "source"}}


@router.get("/jobs/{job_id}/candidates/{candidate_id}")
def get_candidate(job_id: str, candidate_id: int):
    return candidate_detail(job_id, candidate_id)


@router.get("/jobs/{job_id}/candidates/{candidate_id}/export")
def export_candidate(job_id: str, candidate_id: int):
    detail = candidate_detail(job_id, candidate_id)
    value = {"name": f"{detail['seed']['name']}-候选{candidate_id}", "blocks": detail["candidate"]["blocks"],
             "searchMetadata": detail}
    return download(encoded(value), f"候选{candidate_id}.json")


@router.post("/jobs/{job_id}/train")
def train(job_id: str):
    job = active_job(job_id)
    if job["state"] in ("running", "queued"):
        raise HTTPException(409, "任务运行中会自动训练；手动训练请先暂停")
    repository.update(job_id, model=fit_model(job, repository.training_records(job_id)))
    return get_job(job_id)


def provenance(job):
    return digest([{k: s[k] for k in ("id", "hash", "group", "split")} for s in job["seeds"]])


@router.get("/jobs/{job_id}/export")
def export_job(job_id: str):
    job = active_job(job_id)
    records = repository.records(job_id)
    split = {s["id"]: s["split"] for s in job["seeds"]}
    group = {s["id"]: s["group"] for s in job["seeds"]}
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", encoded({"format": "mcscai-search", "version": 1, "job": job,
            "provenance": provenance(job), "featureNames": FEATURE_NAMES,
            "label": "首轮十块负载及时序通过；accepted 才是连续轮次通过"}))
        archive.writestr("candidates.jsonl", "\n".join(encoded({**r, "split": split[r["seed_id"]], "group": group[r["seed_id"]]}) for r in records))
        archive.writestr("train_autodl.py", Path(__file__).with_name("train_autodl.py").read_text())
        archive.writestr("使用说明.txt", "在 AutoDL 选择已有 PyTorch 的镜像，解压后运行：\npython train_autodl.py --data . --output model.json\n"
                          "脚本只使用 train 来源训练，以 validation 来源选择轮次，不读取 test 标签。\n"
                          "在搜索页面暂停任务后上传 model.json，再继续搜索。原始样本与全部修改结果均在本包中。\n"
                          "这是修改评分模型，不是任意需求的结构生成模型。少量样本用 CPU 即可。\n")
    return download(payload.getvalue(), f"{job['name']}-训练数据.zip", "application/zip")


class ImportedModel(BaseModel):
    provenance: str
    featureVersion: Literal[1]
    features: list[str]
    weights: list[float] = Field(min_length=1, max_length=1000)
    trainRows: int = Field(ge=6)
    positive: int = Field(ge=3)
    negative: int = Field(ge=3)
    trainedAt: str = Field(max_length=100)
    validation: dict | None = None


@router.post("/jobs/{job_id}/model")
def import_model(job_id: str, request: ImportedModel):
    job = active_job(job_id)
    if job["state"] in ("running", "queued"):
        raise HTTPException(409, "先暂停任务再导入模型")
    if request.provenance != provenance(job) or request.features != FEATURE_NAMES:
        raise ValueError("模型的数据来源或特征定义与此任务不一致")
    if len(request.weights) != len(FEATURE_NAMES) + 1 or any(not math.isfinite(v) or abs(v) > 1000 for v in request.weights):
        raise ValueError("模型权重格式无效")
    model = {**request.model_dump(), "status": "trained", "kind": "logistic_edit_ranker", "external": True,
             "label": "首轮十块负载及时序通过"}
    repository.update(job_id, model=model)
    return get_job(job_id)
