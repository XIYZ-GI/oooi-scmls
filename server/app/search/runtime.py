import asyncio
import logging
from contextlib import asynccontextmanager
from multiprocessing import get_context

from .worker import run_worker


@asynccontextmanager
async def search_runtime():
    """独立搜索进程退出后恢复未完成任务，服务关闭时限时回收。"""
    context = get_context("spawn")
    stop = context.Event()

    def start():
        process = context.Process(target=run_worker, args=(stop,), daemon=True)
        process.start()
        return process

    worker = start()

    async def supervise():
        nonlocal worker
        while not stop.is_set():
            await asyncio.sleep(5)
            if not stop.is_set() and not worker.is_alive():
                worker.join(timeout=0)
                logging.error("搜索进程退出，正在从服务器记录恢复任务")
                worker = start()

    watcher = asyncio.create_task(supervise())
    try:
        yield
    finally:
        stop.set()
        watcher.cancel()
        try:
            await watcher
        except asyncio.CancelledError:
            pass
        await asyncio.to_thread(worker.join, 3)
        if worker.is_alive():
            worker.terminate()
            await asyncio.to_thread(worker.join, 2)
