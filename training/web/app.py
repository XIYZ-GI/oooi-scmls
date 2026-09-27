"""移动线生成服务的 HTTP 接口；推理在独立子进程里执行，可随时取消。"""

import asyncio
from contextlib import asynccontextmanager, suppress
import gzip
import json
from urllib.parse import quote

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, Response

from ..task import validate_task
from . import repository as repo
from .conditioning import fixed_protocol
from .config import STORE, DEFAULT_CANDIDATES, MAX_CANDIDATES
from .mcstructure import structure_bytes
from .models import CreateJob, Draft, Rename
from .runtime import runtime
from .worker import save_replay
from . import registry


@asynccontextmanager
async def lifespan(_app):
    repo.initialize()
    runner = asyncio.create_task(runtime.loop())
    yield
    runner.cancel()
    with suppress(asyncio.CancelledError):
        await runner


app = FastAPI(title='移动线模型生成', lifespan=lifespan)
PREFIX = '/api/generation'
replay_lock = asyncio.Lock()


@app.exception_handler(ValueError)
async def invalid(_request, error):
    return JSONResponse(status_code=422, content={'detail': str(error)})


@app.exception_handler(KeyError)
async def missing(_request, error):
    return JSONResponse(status_code=404, content={'detail': str(error).strip("'")})


@app.get(PREFIX+'/model')
def model():
    return registry.get()


@app.get(PREFIX+'/models')
def models():
    return registry.catalog()


@app.get(PREFIX+'/draft')
def get_draft():
    return repo.draft()


@app.put(PREFIX+'/draft')
def put_draft(data: Draft):
    payload = data.model_dump(exclude={'revision'})
    # 模型不读每轮刻数与连续轮数时，草稿里也不再保留历史残留值。
    payload['task'] = fixed_protocol(payload['task'], registry.get(payload.get('model_id')))
    return repo.save_draft(data.revision, payload)


@app.get(PREFIX+'/jobs')
def jobs():
    return repo.list_jobs()


@app.post(PREFIX+'/jobs', status_code=202)
def create(data: CreateJob):
    entry = registry.get(data.model_id)
    if not entry['ready']:
        raise HTTPException(503, '所选模型尚未就绪或已禁用')
    task = validate_task(fixed_protocol(data.task.model_dump(), entry))
    return repo.create(task, data.name, data.candidate_count, entry['id'])


def result_for(job_id):
    job = repo.get_job(job_id)
    if job['status'] not in ('success', 'not_found'):
        raise HTTPException(409, '生成尚未完成')
    path = STORE/job_id/'result.json'
    return json.loads(path.read_text())


@app.get(PREFIX+'/jobs/{job_id}')
def detail(job_id: str):
    job = repo.get_job(job_id)
    return {**job, 'result': result_for(job_id) if job['status'] in ('success', 'not_found') else None}


@app.patch(PREFIX+'/jobs/{job_id}')
def rename(job_id: str, data: Rename):
    repo.get_job(job_id)
    if not data.name.strip():
        raise ValueError('名称不能为空')
    repo.update(job_id, name=data.name.strip())
    return repo.get_job(job_id)


@app.post(PREFIX+'/jobs/{job_id}/cancel')
async def cancel(job_id: str):
    await runtime.cancel(job_id)
    return repo.get_job(job_id)


@app.delete(PREFIX+'/jobs/{job_id}')
async def delete(job_id: str):
    await runtime.cancel(job_id)
    repo.update(job_id, deleted=1)
    return {'status': 'ok'}


@app.get(PREFIX+'/jobs/{job_id}/candidates/{index}/replay')
async def replay(job_id: str, index: int):
    result = result_for(job_id)
    if not 0 <= index < len(result['proposals']):
        raise HTTPException(404, '候选不存在')
    async with replay_lock:
        path = STORE/job_id/f'replay-{index}.json.gz'
        if not path.exists():
            task = result['load_tasks'][index] if result.get('load_tasks') else result['task']
            await asyncio.to_thread(save_replay, job_id, index, task, result['proposals'][index])
        with gzip.open(path, 'rt') as handle:
            value = json.load(handle)
    return value


@app.get(PREFIX+'/jobs/{job_id}/candidates/{index}/export')
def export(job_id: str, index: int, assembly: bool = False):
    result = result_for(job_id)
    if not 0 <= index < len(result['proposals']):
        raise HTTPException(404, '候选不存在')
    proposal = result['proposals'][index]
    blocks = list(proposal['blocks'])
    if assembly:
        # 负载按本列最前方方块前两格摆放，与打标器和判定口径一致。
        targets = (result.get('load_tasks') or [result['task']])[index]['targets']
        blocks += [{'position': {'x': t['x'], 'y': t['y'], 'z': t['z']+i}, 'block': {'kind': 'iron_block', 'facing': 'positive_z'}}
                   for t in targets for i in range(10)]
        blocks += [{'position': {**proposal['push'], 'z': proposal['push']['z']-1},
                    'block': {'kind': 'piston', 'facing': 'positive_z'}}]
    filename = repo.get_job(job_id)['name']+f' · 候选{index+1}'+(' · 十负载' if assembly else '')+'.mcstructure'
    # 导出真实结构文件：基岩版小端 NBT，可直接导回游戏或重新上传到打标器。
    return Response(structure_bytes(blocks), media_type='application/octet-stream',
                    headers={'Content-Disposition': f"attachment; filename*=UTF-8''{quote(filename)}"})
