from contextlib import asynccontextmanager
import asyncio
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

store = Store(settings.database_url)
ws = Workspace(settings.workspace_root)
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

init_service(svc)

@asynccontextmanager
async def lifespan(_app):
    worker = asyncio.create_task(run_worker(store, svc))
    try:
        yield
    finally:
        worker.cancel()

app = FastAPI(
    title=settings.app_name,
    version='1.0.0',
    lifespan=lifespan,
)

app.include_router(router)
