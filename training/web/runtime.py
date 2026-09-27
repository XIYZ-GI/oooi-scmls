"""串行调度 CPU 推理，支持取消和服务退出清理。"""

import asyncio
import os
import signal
import sys

from . import repository as repo
from .config import STORE


class Runtime:
    def __init__(self):
        self.current = None
        self.process = None
        self.lock = asyncio.Lock()

    async def cancel(self, job_id):
        async with self.lock:
            job = repo.get_job(job_id)
            if job['status'] not in ('queued', 'running'):
                return
            if self.current == job_id and self.process and self.process.returncode is None:
                try:
                    os.killpg(self.process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    await asyncio.wait_for(self.process.wait(), 3)
                except asyncio.TimeoutError:
                    os.killpg(self.process.pid, signal.SIGKILL)
                    await self.process.wait()
            repo.update(job_id, status='cancelled', message='已取消生成')

    async def loop(self):
        try:
            while True:
                async with self.lock:
                    waiting = [j for j in reversed(repo.list_jobs()) if j['status'] == 'queued']
                    if waiting:
                        self.current = waiting[0]['id']
                        folder = STORE/self.current
                        folder.mkdir(parents=True, exist_ok=True)
                        repo.update(self.current, status='running', message='正在启动 CPU 推理')
                        with (folder/'worker.log').open('a') as log:
                            self.process = await asyncio.create_subprocess_exec(sys.executable, '-m', 'training.web.worker', self.current,
                                stdout=log, stderr=log, start_new_session=True)
                    else:
                        self.current, self.process = None, None
                if self.process:
                    await self.process.wait()
                    try:
                        if repo.get_job(self.current)['status'] == 'running':
                            repo.update(self.current, status='error', message='推理进程退出，可载入需求重新生成')
                    except KeyError:
                        pass
                await asyncio.sleep(.5)
        finally:
            if self.process and self.process.returncode is None:
                await self.cancel(self.current)


runtime = Runtime()
