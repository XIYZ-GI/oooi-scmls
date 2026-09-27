from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import health_router, simulation_router, websocket_router, label_timing_router, library_router
from app.routes import label_replay_router
from app.routes.library import library_exception_handler
from app.repositories import LibraryConflict
from app.services.label_timing import timing_executor
from app.search.api import router as search_router
from app.search.runtime import search_runtime


@asynccontextmanager
async def lifespan(_app: FastAPI):
    async with search_runtime():
        try:
            yield
        finally:
            timing_executor.shutdown(wait=False, cancel_futures=True)

app = FastAPI(
    title="MCSCAI 红石模拟服务",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health_router, prefix="/api")
app.include_router(simulation_router, prefix="/api")
app.include_router(label_timing_router, prefix="/api")
app.include_router(library_router, prefix="/api")
app.include_router(label_replay_router, prefix="/api")
app.include_router(search_router, prefix="/api")
app.add_exception_handler(LibraryConflict, library_exception_handler)
app.add_exception_handler(KeyError, library_exception_handler)
app.add_exception_handler(ValueError, library_exception_handler)
app.include_router(websocket_router, prefix="/ws")
