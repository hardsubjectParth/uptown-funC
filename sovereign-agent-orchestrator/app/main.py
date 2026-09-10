from contextlib import asynccontextmanager
import asyncio
from fastapi import FastAPI
from app.config import settings
from app.storage.store import Store
from app.workspace.manager import Workspace
from app.models.router import ModelRouter
from app.models.adapter import OpenAICompatibleAdapter, FakeModel
from app.policy.engine import Policy
from app.tools.registry import ToolRegistry
from app.verification.verifier import Verifier
from app.orchestrator.service import Orchestrator
from app.rag.service import RagService
from app.api.routes import router, init_service
from app.queue import run_worker

store = Store(settings.database_url)
ws = Workspace(settings.workspace_root)
rag = RagService(
    settings.database_url,
    settings.llm_base_url,
    settings.embedding_model_alias,
    settings.vision_model_alias,
    settings.llm_api_key,
    settings.rerank_model_alias,
    settings.rerank_overfetch,
)

model_router = ModelRouter(settings.model_registry_path)

if settings.model_mode.lower() == 'llamaswap':
    model = OpenAICompatibleAdapter(
        settings.llm_base_url,
        settings.llm_api_key,
        enable_thinking=settings.llm_enable_thinking,
        max_tokens=settings.llm_max_tokens,
    )
else:
    model = FakeModel()

svc = Orchestrator(
    store,
    ws,
    model_router,
    Policy(),
    ToolRegistry(ws, rag, settings.smtp),
    Verifier(ws, settings.require_evidence),
    model,
    settings.use_model_router,
    settings.router_model_alias,
    settings.block_on_injection,
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
