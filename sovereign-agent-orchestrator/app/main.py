from contextlib import asynccontextmanager
import asyncio
import os
from fastapi import FastAPI
from app.config import settings
from app.storage.store import Store
from app.workspace.manager import Workspace
from app.models.router import ModelRouter
from app.models.adapter import OllamaAdapter, FakeModel
from app.policy.engine import Policy
from app.tools.registry import ToolRegistry
from app.verification.verifier import Verifier
from app.orchestrator.service import Orchestrator
from app.rag.service import RagService
from app.api.routes import router, init_service
from app.queue import run_worker
from app.diagnostics import auto_configure, build_capabilities, check_readiness
from app.operations import RuntimeControls, REQUESTS, REQUEST_LATENCY
from time import perf_counter

store = Store(settings.database_url)
ws = Workspace(settings.workspace_root)
auto_configure(settings)
rag = RagService(settings.database_url, settings.ollama_base_url, settings.ollama_embedding_model, settings.ollama_vision_model)

model_router = ModelRouter('config/models.yaml')

if settings.model_mode.lower() == 'ollama':
    model = OllamaAdapter(
        settings.ollama_base_url,
        settings.ollama_model,
    )
else:
    model = FakeModel()

svc = Orchestrator(
    store,
    ws,
    model_router,
    Policy(),
    ToolRegistry(ws, rag),
    Verifier(),
    model,
)
svc.controls = RuntimeControls(store, settings)

svc.capabilities = build_capabilities(settings, store, ws)
svc.readiness = check_readiness(settings, store, ws, svc.capabilities)

init_service(svc)

@asynccontextmanager
async def lifespan(_app):
    svc.readiness = check_readiness(settings, store, ws, svc.capabilities)
    worker = asyncio.create_task(run_worker(store, svc, settings.worker_concurrency)) if os.getenv('RUN_WORKER', 'true').lower() in {'1', 'true', 'yes'} else None
    try:
        yield
    finally:
        if worker:
            worker.cancel()

app = FastAPI(
    title=settings.app_name,
    version='1.0.0',
    lifespan=lifespan,
)

@app.middleware('http')
async def operational_middleware(request, call_next):
    started = perf_counter()
    status = 500
    if not svc.controls.limiter.allow(request.client.host if request.client else 'unknown'):
        status = 429
        from fastapi.responses import JSONResponse
        response = JSONResponse({'detail': 'RATE_LIMIT_EXCEEDED'}, status_code=status)
    else:
        response = await call_next(request)
        status = response.status_code
    elapsed = perf_counter() - started
    path = request.url.path or '/'
    REQUESTS.labels(request.method, path, str(status)).inc()
    REQUEST_LATENCY.labels(request.method, path).observe(elapsed)
    return response

app.include_router(router)
