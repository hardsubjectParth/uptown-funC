# Sovereign Agent Orchestrator

A production-shaped, integration-friendly orchestrator boundary for a local/air-gapped agentic workbench. It implements the vertical slice: **API/CLI → model routing → plan → policy-controlled tools → observe → verify → artifact → REST/SSE frontend contract**.

## What is implemented
- FastAPI REST API with OpenAPI.
- SSE progress stream.
- Deterministic model registry/router.
- LangGraph-compatible orchestration boundary (graph-shaped service; provider-independent adapters).
- Pydantic contracts and exact job states.
- Deterministic policy: allow / deny / require approval.
- Per-job workspace with traversal protection.
- Document search/read/write and DOCX generation.
- Offline document ingestion and retrieval for TXT, Markdown, PDF, DOCX, CSV, XLSX, and image OCR; Ollama embeddings are used when installed and lexical retrieval remains available offline.
- Verification gate and artifact delivery.
- SQLite by default for zero-setup CLI/API; SQLAlchemy also supports PostgreSQL with the included pgvector migrations.
- Fake/local model boundary so the system works without Ollama. Ollama adapter is included for local models.
- No coding workflow in the MVP, per the requested scope; the tool/sandbox extension point remains documented.

## Quick start
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python cli.py
```
The CLI creates `workspace/<job_id>/output/approval_note.docx` and prints the full job JSON.

Run API:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080
```
Then use `/docs`, or:
```bash
curl -X POST http://localhost:8080/api/v1/agent/run -H 'content-type: application/json' -d '{"task":"Read the inspection report and generate an approval note."}'
```

## Architecture
```text
Electron / CLI
    │ REST + SSE
    ▼
FastAPI contract
    │
    ├── Job + Event store
    └── Orchestrator
          │
          ├── Model Router → ModelAdapter → Fake/Ollama
          ├── Planner
          ├── Policy Engine
          ├── Tool Registry → search/read/write/docx
          ├── Observation state
          ├── Verification gate
          ├── Approval pause/resume
          └── Artifact service
```

The frontend sees jobs/events/artifacts only; it does not call models, RAG, databases or tools directly.

## Production wiring
Set `MODEL_MODE=ollama`, configure `OLLAMA_BASE_URL`, and set `DATABASE_URL=postgresql+psycopg://...` for production. Apply `migrations/001_initial_pgvector.sql` and `migrations/002_operational.sql` before startup. Upload and index knowledge with `POST /api/v1/files`, then search it with `POST /api/v1/knowledge/search`. Install `nomic-embed-text` in Ollama for semantic embeddings; without it, deterministic lexical fallback retrieval remains available.

## Test
```bash
pytest -q
```
