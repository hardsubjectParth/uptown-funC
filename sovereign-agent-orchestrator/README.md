# Sovereign Agent Orchestrator
## WHAT THIS ALREADY HAS : 
Core orchestration

Accepts tasks through API or CLI.
Routes tasks to local models.
Runs a plan → act → observe → verify → deliver workflow.
Supports durable jobs and queue processing.
Streams job events through SSE.
Supports approval-required actions.
Generates downloadable artifacts.
Maintains audit events and job history.
Protects job workspaces from path traversal.
RAG capabilities

Ingests TXT, Markdown, PDF, DOCX, CSV, XLSX, XLSM, and images.
Extracts text locally.
Performs OCR with Tesseract or a local vision-model fallback.
Splits documents into overlapping chunks.
Reranks retrieved candidates with a local cross-encoder before answering.
Screens retrieved text for prompt-injection attempts and fences it in the prompt.
Stores documents and chunks in SQLite or PostgreSQL.
Uses local embeddings when the model server is available.
Falls back to lexical search when embeddings are unavailable.
Supports metadata filters such as tenant and clearance.
Avoids duplicate indexing using file checksums.
Supports synchronous ingestion for tools.
Searches indexed documents with source and chunk references.
Report generation

Generates workbook summaries.
Generates DOCX and JSON reports.
Generates knowledge-transfer reports from multiple documents.
Includes source register, transfer checklist, evidence sections, and citations.
Supports --report.
Supports --knowledge-transfer.
``` python 
python cli.py --knowledge-transfer `
  "C:\path\problem.docx" `
  "C:\path\coding-prompt.md" `
  "C:\path\README.md" `
  --output-dir workspace\reports
```

Enabled tools

search_documents
read_file
write_file
generate_docx
ingest_document
list_sources
export_report
spreadsheet_profile
redact_pii
extract_tables
ocr_document
search_db
Communication tools

send_email
create_calendar_event
`create_calendar_event` writes a real RFC 5545 `.ics` file, importable into any
calendar client, and contacts nothing. `send_email` writes a real RFC 5322 `.eml`
file and sends it only when `SMTP_HOST` is configured; with SMTP unset it reports
`external_delivery: false`. Both still require approval under the policy engine.

Data and compliance tools

Spreadsheet profiling
Table extraction
Email and phone redaction
Read-only SQL queries
Source inventory
Controlled report export
Model lineup



Configured in `config/model_registry.yaml` and served by llama-swap
(`config/llama-swap.example.yaml`):

reasoner-35b: Qwen3.6-35B-A3B IQ3_XXS - planning, summaries, approval notes, coding
reasoner-9b: Qwen3.5-9B Q4_K_M - benchmarked alternative
embedder: Qwen3-Embedding-0.6B Q8_0 - RAG embeddings
vision: Qwen3.5-4B Q4_K_M + mmproj - OCR and scanned documents
router: Qwen3.5-2B Q4_K_M - optional LLM task classification
reranker: bge-reranker-v2-m3 Q8_0 - second-stage retrieval scoring (enabled)

llama-swap loads and evicts models on demand, so the set above does not all
run at once.

Files changed

README.md
router.py
policy/engine.py
rag/service.py
rag/report.py
tools/registry.py
cli.py
config/model_registry.yaml
config/llama-swap.example.yaml
config/tools.yaml
tests/test_core.py
ENTERPRISE_RAG_ROADMAP.md
# Sovereign Agent Orchestrator: Offline RAG Integration Guide

This guide explains how to install, run, integrate, and extend the Sovereign Agent Orchestrator on Windows, macOS, and Linux.

The enterprise build plan is in [ENTERPRISE_RAG_ROADMAP.md](../ENTERPRISE_RAG_ROADMAP.md). The model lineup is in [config/model_registry.yaml](config/model_registry.yaml), and the reviewed tool catalog is in [config/tools.yaml](config/tools.yaml).

It also answers an important question directly:

> **Is this a complete offline RAG system?**

**For local document ingestion and retrieval, yes, with an important distinction:**

- It works without internet access and without any model server by using deterministic lexical retrieval.
- It supports local semantic embeddings when llama-swap is running and the embedding GGUF was downloaded before the machine is isolated.
- It supports local vision extraction for images when Tesseract or the local `vision` model is available.
- It is not yet a fully packaged, one-command, air-gapped production appliance. The deployment operator must provide local model files, database backups, secrets, host OCR dependencies, and the production sandbox if arbitrary code execution is added later.

The HTTP API is the primary integration surface. The CLI also attaches `RagService` and supports workbook and multi-document knowledge-transfer reports.

## 1. What the system does

The system accepts a task and optional files, routes the task to a local or fake model, executes only registered tools, verifies the result, and exposes the result and generated artifacts through an API.

For RAG, the flow is:

```text
Document upload
    |
    v
File stored in workspace/uploads
    |
    v
Text extraction
TXT/Markdown/PDF/DOCX/CSV/XLSX/image OCR
    |
    v
Normalized text split into overlapping chunks
    |
    +--> embedding model available: semantic vector stored
    |
    +--> embedding model unavailable: chunk stored without vector
    |
    v
SQLite or PostgreSQL index
    |
    v
Knowledge search
semantic cosine score when possible, lexical score otherwise
    |
    v
Agent tool search_documents or direct search API
```

## 2. Repository map

```text
.
|-- app/
|   |-- main.py                  Application composition and worker lifecycle
|   |-- config.py                Environment-variable settings
|   |-- auth.py                  Bearer API key and tenant identity
|   |-- queue.py                 Durable database-backed job worker
|   |-- api/
|   |   `-- routes.py            REST, SSE, upload, search, approval, artifact routes
|   |-- orchestrator/
|   |   `-- service.py            Plan -> act -> observe -> verify -> deliver workflow
|   |-- models/
|   |   |-- adapter.py            Fake and OpenAI-compatible model adapters
|   |   `-- router.py             Deterministic task-to-model routing
|   |-- rag/
|   |   `-- service.py             Extraction, chunking, embeddings, search
|   |-- tools/
|   |   `-- registry.py            Allowed document and artifact tools
|   |-- policy/
|   |   `-- engine.py              Allow, deny, or approval policy
|   |-- verification/
|   |   `-- verifier.py            Completion and artifact verification
|   |-- storage/
|   |   `-- store.py               Jobs, events, files, approvals, audit, queue
|   |-- workspace/
|   |   `-- manager.py              Per-job filesystem and traversal protection
|   |-- schemas/
|       `-- contracts.py            API request and response contracts
|-- config/
|   |-- model_registry.yaml        Task-to-model-alias routing table
|   `-- llama-swap.example.yaml    Model alias -> llama-server command
|-- migrations/
|   |-- 001_initial_pgvector.sql  PostgreSQL/pgvector schema
|   `-- 002_operational.sql        Operational PostgreSQL tables/indexes
|-- workspace/                     Uploaded files and per-job working data
|-- cli.py                         Local demonstration runner
|-- docker-compose.yml             PostgreSQL plus orchestrator services
|-- Dockerfile                     Container image definition
|-- requirements.txt               Python runtime dependencies
|-- pyproject.toml                 Package metadata and CLI entry point
|-- tests/test_core.py             Core policy, workspace, routing, and RAG tests
|-- README.md                      Short project overview
`-- ARCHITECTURE.md                Internal lifecycle and security notes
```

### Runtime directories

Each job receives its own directory:

```text
workspace/<job_id>/
|-- input/       Files copied from the indexed upload store for this job
|-- working/     Intermediate job files
|-- output/      Generated artifacts exposed through the API
`-- logs/        Reserved for job-specific logs
```

`workspace/uploads/` contains the original files uploaded through `POST /api/v1/files`. The database stores the file record and the RAG database stores document metadata and chunks.

## 3. Prerequisites

### Minimum offline mode

- Python 3.12 or newer
- pip
- No model server required
- SQLite is used by default
- Internet is only needed once to install Python packages, unless wheels are already available locally

This mode supports document extraction and lexical search. It does not provide semantic embeddings or local language-model generation.

### Local semantic and generative mode

Install `llama.cpp` and `llama-swap` on the machine that runs the API, then
download the GGUF models. The full procedure is in
[LLAMA_SWAP_SETUP.md](LLAMA_SWAP_SETUP.md).

The orchestrator talks to one OpenAI-compatible endpoint (`LLM_BASE_URL`) and
selects a model per task by alias, so the same code also works against vLLM or
any other `/v1` server.

Note for macOS: do not run llama.cpp in Docker. Docker Desktop cannot reach the
Metal GPU, so inference would fall back to CPU.

### Image OCR

For image uploads, install Tesseract if you want host-based OCR:

- Windows: install Tesseract OCR and ensure `tesseract.exe` is on `PATH`.
- macOS: `brew install tesseract`
- Debian/Ubuntu: `sudo apt-get install tesseract-ocr`

If Tesseract is unavailable, the service attempts extraction with the local `vision` model. If both are unavailable, the indexed text will contain an OCR-unavailable message and should not be treated as useful evidence.

## 4. Installation: Windows PowerShell

Open PowerShell in the repository directory:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks activation for the current process:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

Start the API with the default offline configuration:

```powershell
$env:MODEL_MODE = "fake"
$env:DATABASE_URL = "sqlite:///./orchestrator.db"
$env:WORKSPACE_ROOT = "./workspace"
uvicorn app.main:app --host 127.0.0.1 --port 8080
```

For local model mode:

```powershell
$env:MODEL_MODE = "llamaswap"
$env:LLM_BASE_URL = "http://127.0.0.1:8080/v1"
llama-swap -config config\llama-swap.yaml -listen :8080
```

In another PowerShell window, download models before disconnecting the machine:

```powershell
# GGUF download commands are in LLAMA_SWAP_SETUP.md
```

## 5. Installation: macOS

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Start the default offline API:

```bash
MODEL_MODE=fake DATABASE_URL=sqlite:///./orchestrator.db \
WORKSPACE_ROOT=./workspace \
uvicorn app.main:app --host 127.0.0.1 --port 8080
```

Install and prepare llama.cpp + llama-swap:

```bash
brew install llama.cpp
# plus the llama-swap release binary - see LLAMA_SWAP_SETUP.md
```

In another terminal:

```bash
MODEL_MODE=llamaswap \
LLM_BASE_URL=http://127.0.0.1:8080/v1 \
uvicorn app.main:app --host 127.0.0.1 --port 8081
```

## 6. Installation: Linux

For Debian or Ubuntu:

```bash
sudo apt-get update
sudo apt-get install -y python3.12 python3.12-venv python3-pip
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Start the default offline API:

```bash
MODEL_MODE=fake DATABASE_URL=sqlite:///./orchestrator.db \
WORKSPACE_ROOT=./workspace \
uvicorn app.main:app --host 127.0.0.1 --port 8080
```

For local model mode, install llama.cpp and llama-swap (see LLAMA_SWAP_SETUP.md), then:

```bash
llama-swap -config config/llama-swap.yaml -listen :8080
```

In another terminal:

```bash
MODEL_MODE=llamaswap \
LLM_BASE_URL=http://127.0.0.1:8080/v1 \
uvicorn app.main:app --host 127.0.0.1 --port 8081
```

## 6A. Generate an offline workbook report

The CLI can ingest an Excel workbook into the local RAG index and generate an aggregate DOCX and JSON report without calling the API or an external service:

```powershell
python cli.py --report "C:\path\to\responses.xlsx" --output-dir workspace\reports
```

The report command supports the same SQLite database and optional local embeddings as the API. If the model server is unavailable, ingestion still succeeds and retrieval uses lexical matching. Generated files are written as `<workbook>_report.docx` and `<workbook>_report.json`.

For a consolidated knowledge-transfer report from multiple documents:

```powershell
python cli.py --knowledge-transfer `
  "C:\path\to\problem-statement.docx" `
  "C:\path\to\coding-prompt.md" `
  "C:\path\to\README.md" `
  --output-dir workspace\reports
```

This creates `knowledge_transfer_report.docx` and `knowledge_transfer_report.json`.

## 7. Configuration

All settings are environment variables. The defaults are suitable for a local development machine.

| Variable | Default | Purpose |
|---|---|---|
| `MODEL_MODE` | `fake` | `fake` avoids model-server dependency; `llamaswap` enables local model calls |
| `DATABASE_URL` | `sqlite:///./orchestrator.db` | Job, file, audit, and RAG storage |
| `WORKSPACE_ROOT` | `./workspace` | Root for uploads and per-job workspaces |
| `LLM_BASE_URL` | `http://localhost:8080/v1` | Local OpenAI-compatible endpoint (llama-swap) |
| `MODEL_REGISTRY_PATH` | `config/model_registry.yaml` | Task-to-model-alias routing table |
| `EMBEDDING_MODEL_ALIAS` | `embedder` | Embedding model alias |
| `VISION_MODEL_ALIAS` | `vision` | Image transcription fallback alias |
| `LLM_ENABLE_THINKING` | `false` | Qwen3.5/3.6 thinking mode; off so `content` holds the answer |
| `LLM_MAX_TOKENS` | `2048` | Generation cap |
| `REQUIRE_EVIDENCE` | `false` | Fail verification when nothing was retrieved |
| `USE_MODEL_ROUTER` | `false` | Classify with the `router` model instead of regex |
| `RERANK_MODEL_ALIAS` | `reranker` | Cross-encoder second-stage retrieval scoring; empty disables |
| `RERANK_OVERFETCH` | `4` | Candidates fetched per final hit before reranking |
| `BLOCK_ON_INJECTION` | `false` | Drop retrieved chunks with injection patterns instead of fencing them |
| `SMTP_HOST` | *(empty)* | Unset means `send_email` drafts a `.eml` and sends nothing |
| `API_KEY` | empty | When set, requires `Authorization: Bearer <API_KEY>` |
| `API_USER_ID` | `api-user` | Default authenticated user identity |
| `API_ROLE` | `user` | Default role; `admin` can access tenant files owned by another user |
| `DEFAULT_TENANT_ID` | `default` | Tenant used when `X-Tenant-Id` is absent |
| `DEFAULT_CLEARANCE` | `internal` | Clearance attached to the request identity |
| `API_HOST` | `0.0.0.0` | Application host setting |
| `API_PORT` | `8080` | Application port setting |
| `MAX_ITERATIONS` | `3` | Orchestrator iteration limit |
| `MAX_TOOL_CALLS` | `12` | Orchestrator tool-call limit |
| `JOB_TIMEOUT_SECONDS` | `120` | Job timeout |
| `TOOL_TIMEOUT_SECONDS` | `30` | Tool timeout |

For anything beyond a single-user local machine, set `API_KEY`, use a non-default tenant ID, restrict network exposure, and put the service behind a TLS-terminating reverse proxy or private network.

## 8. Verify that the API is running

Open the interactive API contract at:

```text
http://127.0.0.1:8080/docs
```

Health checks:

```bash
curl http://127.0.0.1:8080/api/v1/health
curl http://127.0.0.1:8080/api/v1/ready
```

Expected response:

```json
{"status":"ok"}
```

When `API_KEY` is set, add these headers to every protected request:

```text
Authorization: Bearer your-local-api-key
X-Tenant-Id: engineering
```

The health endpoints do not require authentication.

## 9. Upload and index documents

Upload a supported file:

```bash
curl -X POST http://127.0.0.1:8080/api/v1/files \
  -H "Authorization: Bearer your-local-api-key" \
  -H "X-Tenant-Id: engineering" \
  -F "file=@./documents/inspection-report.pdf"
```

On Windows PowerShell, use:

```powershell
curl.exe -X POST http://127.0.0.1:8080/api/v1/files `
  -H "Authorization: Bearer your-local-api-key" `
  -H "X-Tenant-Id: engineering" `
  -F "file=@.\documents\inspection-report.pdf"
```

Supported extensions:

```text
.txt .md .pdf .docx .csv .xlsx .xlsm .png .jpg .jpeg .tiff .bmp
```

The response includes `file_id`, which is required to attach the upload to an agent job. The response also reports whether chunks were embedded.

## 10. Search the knowledge base directly

```bash
curl -X POST http://127.0.0.1:8080/api/v1/knowledge/search \
  -H "content-type: application/json" \
  -H "Authorization: Bearer your-local-api-key" \
  -H "X-Tenant-Id: engineering" \
  -d '{"query":"fire extinguisher inspection interval","top_k":5}'
```

The service chooses the score automatically:

- If both the query and chunk have embeddings, it uses cosine similarity.
- Otherwise, it uses a deterministic token-overlap lexical score.

Tenant metadata is always added to the search filter by the API route. Additional metadata can be supplied in the request when the indexed metadata contains the same keys.

## 11. Run an agent task with indexed files

Start a job using the `file_id` returned by upload:

```bash
curl -X POST http://127.0.0.1:8080/api/v1/agent/run \
  -H "content-type: application/json" \
  -H "Authorization: Bearer your-local-api-key" \
  -H "X-Tenant-Id: engineering" \
  -d '{
    "task":"Read the inspection report, find the applicable SOP requirements, and generate an approval note with citations.",
    "attachments":[{"file_id":"REPLACE_WITH_THE_RETURNED_FILE_ID"}],
    "user_context":{"user_id":"analyst-1","role":"user","department":"inspection","clearance":"internal","project":"demo"}
  }'
```

The API returns a `job_id` immediately. Poll the job:

```bash
curl http://127.0.0.1:8080/api/v1/agent/JOB_ID \
  -H "Authorization: Bearer your-local-api-key" \
  -H "X-Tenant-Id: engineering"
```

Stream progress using Server-Sent Events:

```bash
curl -N http://127.0.0.1:8080/api/v1/agent/JOB_ID/events \
  -H "Authorization: Bearer your-local-api-key" \
  -H "X-Tenant-Id: engineering"
```

List and download generated artifacts:

```bash
curl http://127.0.0.1:8080/api/v1/agent/JOB_ID/artifacts \
  -H "Authorization: Bearer your-local-api-key" \
  -H "X-Tenant-Id: engineering"

curl -L http://127.0.0.1:8080/api/v1/agent/JOB_ID/artifacts/approval_note.docx \
  -H "Authorization: Bearer your-local-api-key" \
  -H "X-Tenant-Id: engineering" \
  -o approval_note.docx
```

## 12. Approval and cancellation

Some policy-controlled actions can pause at `awaiting_approval`.

Approve:

```bash
curl -X POST http://127.0.0.1:8080/api/v1/agent/JOB_ID/approve \
  -H "content-type: application/json" \
  -H "Authorization: Bearer your-local-api-key" \
  -H "X-Tenant-Id: engineering" \
  -d '{"approved":true,"reviewer_user_id":"reviewer-1"}'
```

Reject:

```bash
curl -X POST http://127.0.0.1:8080/api/v1/agent/JOB_ID/approve \
  -H "content-type: application/json" \
  -H "Authorization: Bearer your-local-api-key" \
  -H "X-Tenant-Id: engineering" \
  -d '{"approved":false,"reviewer_user_id":"reviewer-1"}'
```

Cancel:

```bash
curl -X POST http://127.0.0.1:8080/api/v1/agent/JOB_ID/cancel \
  -H "Authorization: Bearer your-local-api-key" \
  -H "X-Tenant-Id: engineering"
```

## 13. API integration pattern

An Electron, web, or desktop client should only call the API. It should not import model, RAG, database, or tool modules directly.

Recommended client sequence:

```text
1. GET /health
2. POST /files for each knowledge document
3. Save each returned file_id
4. POST /agent/run with task, user_context, and attachment file_ids
5. Subscribe to /agent/{job_id}/events
6. GET /agent/{job_id} when the stream ends
7. If status is awaiting_approval, POST /approve
8. GET /agent/{job_id}/artifacts
9. Download artifacts through the artifact endpoint
```

The frontend receives job IDs, event data, final answers, and API artifact URLs. Host filesystem paths must remain server-side.

## 14. Docker and PostgreSQL

The Compose file starts PostgreSQL with pgvector and the orchestrator. It does not start a model server; the default Compose configuration uses `MODEL_MODE=fake`.

Start it:

```bash
docker compose up --build
```

The database is initialized from the migration files mounted into PostgreSQL's initialization directory. Persistent data is stored in the `postgres_data` volume, and the local `workspace` directory is mounted into the orchestrator container.

For semantic embeddings in Docker, llama-swap must be reachable from the orchestrator container. `localhost` inside the container is the container itself, not the host: set `LLM_BASE_URL` to the host gateway (`http://host.docker.internal:8080/v1`) or to a separately managed inference service. On macOS, run llama.cpp on the host rather than in a container - Docker Desktop cannot reach the Metal GPU.

Before an air-gapped deployment:

```text
1. Pull the pgvector image.
2. Build the orchestrator image.
3. Pull and cache all Python packages or build from an internal package mirror.
4. Download and cache the GGUF model files.
5. Export/import the images and model files on the isolated network.
6. Keep database and workspace volumes on persistent storage.
```

Do not use the sample PostgreSQL password in a real deployment. Supply secrets through the deployment environment or a secret manager.

## 15. SQLite versus PostgreSQL

SQLite is the simplest choice for a single-user or development deployment:

```text
DATABASE_URL=sqlite:///./orchestrator.db
```

PostgreSQL is the better choice for multiple workers, concurrent users, backups, and operational monitoring:

```text
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE
```

The RAG service creates its basic tables at startup. For PostgreSQL production deployments, apply both migration files and confirm that the pgvector extension is enabled. Keep the database, `workspace/uploads`, and `workspace/<job_id>/output` in the backup plan.

## 16. What is complete and what still needs work

### Complete for the current scope

- Local HTTP API and OpenAPI documentation
- SQLite zero-setup mode
- PostgreSQL and pgvector migration path
- Tenant-aware upload and attachment authorization
- Durable jobs, events, approvals, audit records, and queue rows
- Per-job workspace traversal protection
- TXT, Markdown, PDF, DOCX, CSV, XLSX, XLSM, and common image ingestion
- Deterministic chunking
- Optional local embeddings via the `embedder` model
- Lexical retrieval fallback with no model server
- Optional Tesseract and local vision-model extraction
- Agent document search tool
- DOCX artifact generation
- SSE progress events
- Fake model path for integration tests without a model server

### Required before calling it a production air-gapped appliance

- A pinned offline Python wheelhouse or internal package index
- A documented model acquisition and checksum process
- A managed llama-swap/llama.cpp service or another local inference runtime
- Resource limits and model sizing for the target hardware
- Authentication and authorization beyond the environment-variable identity shim
- TLS or a private network boundary
- Database backup, restore, migration, and retention procedures
- File-size, request-size, rate-limit, and quota controls
- Malware scanning and content validation for uploaded files
- OCR quality monitoring and explicit handling for scanned PDFs
- Evaluation data for retrieval precision, recall, and citation correctness
- A production sandbox if new tools execute code or external processes
- Monitoring, structured logs, alerting, and worker restart policy
- A fix or explicit design decision for the standalone CLI's missing RAG service wiring

The current system intentionally has no arbitrary URL fetch tool and no coding sandbox. Those are security-sensitive extensions, not missing convenience features.

## 17. Recommended offline acceptance test

Run the test suite:

```bash
pytest -q
```

Then validate the actual deployment in this order:

```text
1. Stop network access.
2. Start the API with MODEL_MODE=fake.
3. Upload a TXT or CSV file.
4. Search for an exact phrase and confirm a hit.
5. Start an agent job with the file attached.
6. Confirm events move through the job lifecycle.
7. Download the generated artifact.
8. Start llama-swap, if used, and repeat with semantic queries.
9. Upload an image and verify either Tesseract or local vision extraction.
10. Restart the service and confirm jobs, files, and indexed chunks remain available.
11. Test a second tenant and confirm it cannot search or attach the first tenant's files.
12. Restore from a database and workspace backup on a separate machine.
```

A deployment passes the offline RAG portion only when it can complete steps 1 through 7 with the network disabled. Semantic and image-vision tests are additional capabilities and require their local model or OCR dependencies.

## 18. Useful source files

- [README.md](README.md): concise project overview
- [ARCHITECTURE.md](ARCHITECTURE.md): lifecycle, security invariants, and extension points
- [app/rag/service.py](app/rag/service.py): extraction, chunking, embedding, and retrieval implementation
- [app/api/routes.py](app/api/routes.py): upload, search, agent, SSE, and artifact endpoints
- [app/config.py](app/config.py): environment-variable defaults
- [app/auth.py](app/auth.py): current API identity behavior
- [app/tools/registry.py](app/tools/registry.py): allowed tool surface
- [app/storage/store.py](app/storage/store.py): persistence and queue behavior
- [docker-compose.yml](docker-compose.yml): PostgreSQL deployment example
- [tests/test_core.py](tests/test_core.py): current automated coverage


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
- Offline document ingestion and retrieval for TXT, Markdown, PDF, DOCX, CSV, XLSX, and image OCR; local embeddings are used when the model server is running and lexical retrieval remains available offline.
- Verification gate and artifact delivery.
- SQLite by default for zero-setup CLI/API; SQLAlchemy also supports PostgreSQL with the included pgvector migrations.
- Fake/local model boundary so the system works with no model server. An OpenAI-compatible adapter drives local models.
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
          ├── Model Router → ModelAdapter → Fake/OpenAI-compatible
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
Set `MODEL_MODE=llamaswap`, configure `LLM_BASE_URL`, and set `DATABASE_URL=postgresql+psycopg://...` for production. Apply `migrations/001_initial_pgvector.sql` and `migrations/002_operational.sql` before startup. Upload and index knowledge with `POST /api/v1/files`, then search it with `POST /api/v1/knowledge/search`. Run the `embedder` model for semantic embeddings; without it, deterministic lexical fallback retrieval remains available.

## Test
```bash
pytest -q
```
