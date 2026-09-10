# Sovereign Agent Orchestrator

A fully local ("sovereign") agent backend for document workflows. It accepts a
task, routes it to an appropriate local model, retrieves supporting documents,
runs a policy-controlled tool plan, verifies the result, and delivers a cited
artifact. **No cloud calls** — inference, embeddings, reranking and retrieval all
run on the machine.

The HTTP API is the integration surface. A dashboard or desktop client talks only
to the API; it never imports model, RAG, database or tool modules.

---

## Contents

1. [Quick start](#1-quick-start)
2. [How it works](#2-how-it-works)
3. [API reference](#3-api-reference) ← dashboard integration
4. [Dashboard integration guide](#4-dashboard-integration-guide)
5. [Configuration](#5-configuration)
6. [Models](#6-models)
7. [Tools and policy](#7-tools-and-policy)
8. [Operations](#8-operations)
9. [Handoff notes](#9-handoff-notes)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Quick start

### Requirements

- Python 3.12+
- ~26 GB disk for models (only for real-model mode)
- 32 GB RAM recommended; see [Operations](#8-operations) for the memory envelope

### Install

```bash
cd sovereign-agent-orchestrator
uv venv --python 3.12          # or: python3.12 -m venv .venv
uv pip install -r requirements.txt
```

### Run without any model server

`MODEL_MODE=fake` exercises the entire pipeline with a deterministic stub. This
is what the test suite uses and the fastest way to verify an install:

```bash
.venv/bin/python -m pytest -q                    # expect: 35 passed
MODEL_MODE=fake .venv/bin/python cli.py "summarize the inspection report"
```

### Run with real local models

Full procedure — installing llama.cpp and llama-swap, downloading the GGUFs — is
in **[LLAMA_SWAP_SETUP.md](LLAMA_SWAP_SETUP.md)**. Once that is done:

```bash
# 1. start the model server (port 8080)
llama-swap -config config/llama-swap.yaml -listen :8080

# 2. start the API (port 8081 — keep it OFF 8080)
export MODEL_MODE=llamaswap
export LLM_BASE_URL=http://localhost:8080/v1
export DATABASE_URL=sqlite:///./orchestrator.db
export WORKSPACE_ROOT=./workspace
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8081
```

Verify: <http://127.0.0.1:8081/docs> (interactive API browser) and
`curl http://127.0.0.1:8081/api/v1/health`.

### Try it with the included samples

```bash
python - <<'PY'
import asyncio, glob
from app.rag.service import RagService
rag = RagService('sqlite:///./orchestrator.db', 'http://localhost:8080/v1', 'embedder', 'vision')
for f in glob.glob('samples/*.md'):
    print(asyncio.run(rag.ingest(f, {'tenant_id': 'default', 'clearance': 'internal'})))
PY
```

See [samples/README.md](samples/README.md) — one document deliberately contains a
prompt-injection attack, so you can watch the guardrail fire.

---

## 2. How it works

```
POST /agent/run
      │
      ▼
  Router ──────────► picks a model alias from config/model_registry.yaml
      │                (regex, or the `router` model if USE_MODEL_ROUTER=true)
      ▼
  RAG retrieval ───► embeddings → overfetch → cross-encoder rerank → top_k
      │
      ▼
  Injection screen ► retrieved text checked, fenced in <document> tags
      │
      ▼
  Model call ──────► OpenAI-compatible /v1/chat/completions (llama-swap)
      │
      ▼
  Plan ────────────► document workflow, coding workflow, or none
      │
      ▼
  Policy ──────────► allow / deny / require_approval per tool
      │
      ▼
  Tools ───────────► search, docx generation, file writes, …
      │
      ▼
  Verification ────► plan complete, citations present, artifacts exist, grounded
      │
      ▼
  Artifact ────────► .docx with Evidence / Provenance / References, or source files
```

Jobs are durable: they are written to the database and processed by a background
worker, so a restart resumes queued work. Every step emits an event, streamed to
clients over SSE.

---

## 3. API reference

Base URL: `http://<host>:8081/api/v1`
Interactive browser: `http://<host>:8081/docs`
OpenAPI schema: `http://<host>:8081/openapi.json`

### Authentication

| header | when | notes |
|---|---|---|
| `Authorization: Bearer <API_KEY>` | required when `API_KEY` is set | if `API_KEY` is empty, auth is **disabled** — fine locally, never in production |
| `X-Tenant-Id: <tenant>` | optional | defaults to `DEFAULT_TENANT_ID`. Scopes files and jobs; a tenant cannot read another tenant's jobs or attach their files |

`/health` and `/ready` never require auth.

### Endpoints

| method | path | purpose |
|---|---|---|
| `GET` | `/health` | liveness — `{"status":"ok"}` |
| `GET` | `/ready` | readiness — `{"status":"ready"}` |
| `POST` | `/files` | upload + index a document |
| `POST` | `/knowledge/search` | search the index directly |
| `POST` | `/agent/run` | start a job |
| `GET` | `/agent/{job_id}` | full job state |
| `GET` | `/agent/{job_id}/events` | SSE progress stream |
| `POST` | `/agent/{job_id}/approve` | approve or reject a paused job |
| `POST` | `/agent/{job_id}/cancel` | cancel a job |
| `GET` | `/agent/{job_id}/artifacts` | list generated artifacts |
| `GET` | `/agent/{job_id}/artifacts/{name}` | download one artifact |

---

### `POST /files`

`multipart/form-data`, field name `file`. Extracts text, chunks it, embeds each
chunk, and stores it in the index.

Supported: `.txt .md .pdf .docx .csv .xlsx .xlsm .png .jpg .jpeg .tiff .bmp`
(images go through OCR — Tesseract if installed, otherwise the `vision` model).

```bash
curl -X POST http://127.0.0.1:8081/api/v1/files \
  -H "Authorization: Bearer $API_KEY" -H "X-Tenant-Id: engineering" \
  -F "file=@./report.pdf"
```

```json
{
  "file_id": "7b85f63d-1722-4295-99f5-4b87ce7be306",
  "name": "report.pdf",
  "mime_type": "application/pdf",
  "size_bytes": 1045,
  "index": {"document_id": "1ff06c09-…", "name": "report.pdf", "chunks": 7, "embedded": 7}
}
```

`embedded` < `chunks` means the embedding model was unreachable; retrieval falls
back to lexical matching. Returns **400** for an unsupported file type.

Keep `file_id` — it is how you attach the document to a job.

---

### `POST /knowledge/search`

```json
{"query": "extinguisher overdue service", "top_k": 5, "metadata": {}}
```

```json
{"hits": [{
  "chunk_id": "5a3a72f8-…",
  "source": "inspection-2026-03.md",
  "content": "…",
  "score": 0.914218,
  "retrieval_score": 0.414,
  "rerank_logit": -2.27,
  "reranked": true,
  "metadata": {"tenant_id": "default"}
}]}
```

`score` is the final ranking score (reranker when enabled, otherwise embedding
cosine). `retrieval_score` preserves the embedding score so you can show how
reranking changed the order. Returns **422** if `query` is empty.

---

### `POST /agent/run`

```json
{
  "task": "Read the inspection report and write an approval note citing the SOP.",
  "user_context": {
    "user_id": "analyst-1",
    "role": "user",
    "department": "inspection",
    "clearance": "internal",
    "project": "demo"
  },
  "attachments": [{"file_id": "7b85f63d-…"}]
}
```

Only `task` is required. `role: "approver_demo"` forces document generation
through the approval gate — useful for demonstrating that flow.

Returns immediately; the job runs in the background:

```json
{"job_id": "0c28e2c0-…", "status": "queued"}
```

Returns **422** if an attachment has no `file_id`, **403** if the caller may not
use that file.

---

### `GET /agent/{job_id}`

The full job document. Key fields:

| field | meaning |
|---|---|
| `status` | see [job statuses](#job-statuses) |
| `routing` | `{registry_task, model_alias, task_type, classifier, confidence, reason, fallback_alias}` |
| `retrieval` | the retrieved chunks with scores — the evidence used |
| `injection_findings` | present when retrieved content contained prompt-injection patterns |
| `plan` | the steps, each with `tool`, `tool_args`, `status` |
| `tool_calls` | each call with `risk_tier` and `policy_decision` |
| `verification` | `{passed, checks{…}, notes[]}` |
| `requires_human_approval`, `approval` | set when paused at `awaiting_approval` |
| `artifacts` | `[{artifact_id, name, mime_type, size_bytes, url}]` |
| `final_answer` | the answer text |
| `model_response` | `{content, reasoning_content, finish_reason, usage, model}` |
| `error` | failure reason, `null` on success |

Returns **404** if the job does not exist *or* belongs to another tenant.

#### Job statuses

`queued` → `planning` → `acting` → `observing` → `verifying` → `delivering` → `done`

Plus: `awaiting_approval` (paused, needs `/approve`), `failed`, `cancelled`.

Terminal states are **`done`, `failed`, `cancelled`** — the SSE stream closes on
these.

#### Verification checks

| check | blocks delivery? | meaning |
|---|---|---|
| `plan_completed` | yes | every step finished |
| `citations_present` | yes | document workflows carry citations |
| `citation_sources_valid` | yes | every hit has a real chunk id and source |
| `artifacts_exist` | yes | a file was produced |
| `no_unhandled_denials` | yes | no tool was denied by policy |
| `evidence_grounded` | only if `REQUIRE_EVIDENCE=true` | the answer is backed by retrieved evidence |
| `no_injection_detected` | **never** | advisory; retrieved text contained injection patterns |

---

### `GET /agent/{job_id}/events` — SSE

`text/event-stream`. Each event has an SSE `event:` type and a JSON `data:`
payload `{event_id, type, data, timestamp}`. The server polls every 250 ms and
**closes the stream** once the job reaches a terminal state.

| event | when | useful payload |
|---|---|---|
| `job_created` | accepted | `status` |
| `status_changed` | every transition | `status` |
| `model_selected` | after routing | the full routing decision |
| `injection_detected` | injection found in retrieved text | `findings[]` |
| `model_response` | model replied | `model_id`, `response` |
| `model_fallback` | primary alias failed, retried | `from`, `to`, `error` |
| `model_error` | model call failed | `error`, `model_id` |
| `plan_created` | plan built | `steps[]` |
| `step_started` / `step_completed` | per plan step | `step_id` |
| `tool_started` | before a tool runs | `tool`, `risk_tier`, `policy_decision` |
| `tool_completed` | after a tool runs | `call_id`, `result` |
| `observation` | tool outputs collected | `summary` |
| `verification_passed` / `verification_failed` | gate result | `checks`, `notes` |
| `approval_required` | paused | `risk_tier`, `reason`, `pending_tool` |
| `approval_approved` / `approval_rejected` | decision recorded | approval object |
| `artifact_created` | files ready | `artifacts[]` |
| `job_completed` | finished | `final_answer` |
| `job_cancelled` | cancelled | — |
| `worker_error` | unhandled worker failure | `error` |

⚠️ **The browser `EventSource` API cannot send custom headers.** If `API_KEY` is
set, either proxy the stream through your dashboard's backend, or use a
`fetch()`-based SSE reader (example in
[§4](#4-dashboard-integration-guide)).

---

### `POST /agent/{job_id}/approve`

```json
{"approved": true, "reviewer_user_id": "reviewer-1"}
```

Resumes the pending tool and continues to verification and delivery. `false`
fails the job with `APPROVAL_REJECTED`. Returns **409** unless the job is
currently `awaiting_approval`.

### `POST /agent/{job_id}/cancel`

Marks the job `cancelled`.

### `GET /agent/{job_id}/artifacts` and `/artifacts/{name}`

The list endpoint returns artifact metadata; the second streams the file with the
correct MIME type. Paths are confined to the job's `output/` directory —
traversal attempts raise `PATH_OUTSIDE_JOB_WORKSPACE`.

---

## 4. Dashboard integration guide

### Recommended sequence

```
1. GET  /health                              is the backend up
2. POST /files            per document       keep each file_id
3. POST /agent/run        task + file_ids    keep job_id
4. GET  /agent/{id}/events                   stream progress
5. GET  /agent/{id}                          on stream close, read final state
6. POST /agent/{id}/approve                  if status == awaiting_approval
7. GET  /agent/{id}/artifacts                list outputs
8. GET  /agent/{id}/artifacts/{name}         download
```

### Minimal client

```js
const BASE = 'http://127.0.0.1:8081/api/v1';
const headers = { 'Authorization': `Bearer ${API_KEY}`, 'X-Tenant-Id': 'engineering' };

// 1. upload
const form = new FormData();
form.append('file', fileInput.files[0]);
const { file_id } = await (await fetch(`${BASE}/files`, {
  method: 'POST', headers, body: form,
})).json();

// 2. start the job
const { job_id } = await (await fetch(`${BASE}/agent/run`, {
  method: 'POST',
  headers: { ...headers, 'content-type': 'application/json' },
  body: JSON.stringify({ task: 'Summarize the findings and cite the SOP.',
                         attachments: [{ file_id }] }),
})).json();

// 3. stream progress (fetch-based: EventSource cannot send headers)
const res = await fetch(`${BASE}/agent/${job_id}/events`, { headers });
const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
let buffer = '';
while (true) {
  const { value, done } = await reader.read();
  if (done) break;
  buffer += value;
  const frames = buffer.split('\n\n');
  buffer = frames.pop();
  for (const frame of frames) {
    const type = frame.match(/^event: (.+)$/m)?.[1];
    const data = JSON.parse(frame.match(/^data: (.+)$/m)[1]);
    onEvent(type, data);          // drive your progress UI
  }
}

// 4. final state + artifacts
const job = await (await fetch(`${BASE}/agent/${job_id}`, { headers })).json();
if (job.status === 'awaiting_approval') { /* show the approval dialog */ }
for (const a of job.artifacts) {
  // a.url is already an API path: /api/v1/agent/{id}/artifacts/{name}
}
```

### What to surface in the UI

- **Progress** — drive from `status_changed`; the ordered statuses make a natural
  stepper.
- **Which model ran** — `routing.model_alias` and `routing.registry_task`. Users
  of a multi-model system want to see the choice.
- **Evidence** — render `retrieval[]`: source, score, and the chunk text. This is
  what makes an answer auditable.
- **⚠ Injection warnings** — if `injection_findings` is non-empty, show a
  prominent banner. The document itself carries the warning, but the operator
  should see it before opening the file.
- **Approvals** — when `status === 'awaiting_approval'`, show
  `approval.pending_tool` and `approval.reason` with approve/reject buttons.
- **Verification** — `verification.checks` maps cleanly to a checklist; show
  `notes[]` as warnings.

### Notes for client authors

- Jobs are **asynchronous**. `POST /agent/run` returns before any work happens.
- The **first request after idle takes ~10 s** while llama-swap loads a model.
  Do not set a short client timeout; 5 minutes is reasonable.
- The **stream ends by itself** at a terminal state — treat close as completion
  and re-fetch the job.
- Artifact `url` values are **API paths, not filesystem paths**. Host paths are
  never exposed to clients.
- A tenant sees only its own jobs and files. Cross-tenant access returns 404/403,
  not an empty result.

---

## 5. Configuration

All configuration is environment variables. Copy `.env.example` and edit.

### Core

| variable | default | purpose |
|---|---|---|
| `MODEL_MODE` | `fake` | `fake` = no model server; `llamaswap` = real models |
| `LLM_BASE_URL` | `http://localhost:8080/v1` | OpenAI-compatible endpoint |
| `LLM_API_KEY` | *(empty)* | bearer token for that endpoint, if proxied |
| `DATABASE_URL` | `sqlite:///./orchestrator.db` | jobs, files, audit, RAG index |
| `WORKSPACE_ROOT` | `./workspace` | per-job scratch and artifacts |
| `MODEL_REGISTRY_PATH` | `config/model_registry.yaml` | task → model alias table |
| `API_HOST` / `API_PORT` | `0.0.0.0` / `8080` | informational; uvicorn flags win |

### Models and generation

| variable | default | purpose |
|---|---|---|
| `EMBEDDING_MODEL_ALIAS` | `embedder` | embedding model alias |
| `VISION_MODEL_ALIAS` | `vision` | image transcription alias |
| `RERANK_MODEL_ALIAS` | `reranker` | cross-encoder; empty disables reranking |
| `RERANK_OVERFETCH` | `4` | candidates fetched per final hit |
| `LLM_ENABLE_THINKING` | `false` | Qwen3.5/3.6 thinking mode — see warning below |
| `LLM_MAX_TOKENS` | `2048` | generation cap |
| `USE_MODEL_ROUTER` | `false` | classify with the `router` model instead of regex |
| `ROUTER_MODEL_ALIAS` | `router` | classifier alias |

⚠️ **Leave `LLM_ENABLE_THINKING=false` unless you also raise `LLM_MAX_TOKENS`.**
Qwen3.5/3.6 emit chain-of-thought into `reasoning_content` and fill `content`
only afterwards; if the budget runs out mid-thought the answer is empty.

### Security and policy

| variable | default | purpose |
|---|---|---|
| `API_KEY` | *(empty)* | when set, requires `Authorization: Bearer` — **set this in production** |
| `DEFAULT_TENANT_ID` | `default` | tenant when `X-Tenant-Id` is absent |
| `DEFAULT_CLEARANCE` | `internal` | clearance attached to the identity |
| `API_USER_ID` / `API_ROLE` | `api-user` / `user` | identity shim; `admin` can read tenant files owned by others |
| `REQUIRE_EVIDENCE` | `false` | fail verification when nothing was retrieved |
| `BLOCK_ON_INJECTION` | `false` | drop flagged chunks instead of fencing them |

### Outbound email (opt-in)

| variable | default | purpose |
|---|---|---|
| `SMTP_HOST` | *(empty)* | **empty = nothing is ever sent**; `send_email` still writes a `.eml` |
| `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_FROM` / `SMTP_USE_TLS` | `587` / — / — / — / `true` | delivery settings |

---

## 6. Models

Served by `llama-swap`, which loads and evicts models on demand, so many are
available without running them all at once. Aliases are the contract between
`config/model_registry.yaml` (which task uses which alias) and
`config/llama-swap.yaml` (which alias runs which file).

| alias | model | quant | size | resident | role |
|---|---|---|---|---|---|
| `reasoner-35b` | Qwen3.6-35B-A3B | UD-IQ3_XXS | 13.2 GB | on demand | **default reasoner** — planning, summaries, analysis, approval notes, coding |
| `reasoner-9b` | Qwen3.5-9B | Q4_K_M | 5.7 GB | on demand | benchmarked alternative |
| `embedder` | Qwen3-Embedding-0.6B | Q8_0 | 0.64 GB | yes | RAG embeddings (1024-dim) |
| `reranker` | bge-reranker-v2-m3 | Q8_0 | 0.61 GB | yes | cross-encoder rerank |
| `vision` | Qwen3.5-4B + mmproj | Q4_K_M | 3.4 GB | on demand | OCR, scanned documents |
| `router` | Qwen3.5-2B | Q4_K_M | 1.28 GB | yes | optional task classification |

Changing the reasoner is one line — `model_alias` in `config/model_registry.yaml`.
Rationale for these choices, including measurements, is in
[CHANGES.md](CHANGES.md) §4C and §4E.

---

## 7. Tools and policy

Tools are the only actions the agent can take. Unknown tools are denied.

| tool | risk | decision |
|---|---|---|
| `search_documents`, `read_file`, `ingest_document`, `list_sources`, `spreadsheet_profile`, `extract_tables`, `ocr_document` | 0 | allow |
| `write_file`, `generate_docx`, `export_report`, `redact_pii`, `search_db` | 1 | allow |
| `send_email`, `create_calendar_event` | 2 | **require approval** |

`generate_docx` also requires approval when `user_context.role == "approver_demo"`.

`search_db` accepts read-only `SELECT`/`WITH` queries only and rejects anything
containing `;`. There is deliberately **no arbitrary URL fetch and no code
execution sandbox** — see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## 8. Operations

### Ports

| port | service |
|---|---|
| 8080 | llama-swap (model server) |
| 8081 | this API — **keep it off 8080** |

### Memory envelope (measured, 32 GB M1 Max)

| configuration | wired |
|---|---|
| `reasoner-35b` (IQ3_XXS, `-c 16384`) alone | 18.2 GB |
| + `embedder` alongside | 20.1 GB |
| + a 10,640-token prompt in flight | 20.1 GB |
| the same model at **Q4** (22.13 GB) | ✗ 500 `Compute error` |

Practical ceiling ≈ 22 GB. `-c` is charged **on top of** the weights, so raising
context costs memory. `-c 16384` is the tested value.

### Storage

SQLite by default. For multiple workers, concurrent users or backups, use
PostgreSQL + pgvector:

```bash
DATABASE_URL=postgresql+psycopg://user:password@host:5432/orchestrator
```

Apply `migrations/001_initial_pgvector.sql` and `migrations/002_operational.sql`
first. Back up the database, `workspace/uploads/`, and each
`workspace/<job_id>/output/`.

### Where things live

```text
sovereign-agent-orchestrator/
├── app/                  application code
├── config/               model registry + llama-swap config
├── samples/              committed test documents
├── migrations/           PostgreSQL schema
└── workspace/            per-job scratch and artifacts (gitignored)

~/sovereign-agent/        deployment data, outside the repo
├── models/               GGUF files (~25 GB)
├── documents/inbox/      documents to index
└── artifacts/            generated outputs worth keeping
```

`config/llama-swap.yaml` is gitignored (absolute paths);
`config/llama-swap.example.yaml` is the shared template.

### Docker

`docker-compose.yml` runs PostgreSQL and the orchestrator. It does **not** run
the model server.

⚠️ **Do not run llama.cpp in Docker on macOS** — Docker Desktop cannot reach the
Metal GPU, so inference falls back to CPU. Run llama-swap on the host and point
`LLM_BASE_URL` at `http://host.docker.internal:8080/v1`. On Linux with the NVIDIA
Container Toolkit, containerising the model server is fine.

---

## 9. Handoff notes

### Working and verified

- End-to-end document workflow against real local models, producing a `.docx`
  with evidence citations
- Coding workflow producing source files instead of a document
- RAG: extraction, chunking, local embeddings, cross-encoder reranking, tenant
  filtering, lexical fallback when the embedder is unavailable
- Prompt-injection detection, prompt fencing, and reporting — verified against a
  poisoned document; the model refused the attack
- Durable jobs, SSE events, approval pause/resume, audit records
- Per-job workspace with path-traversal protection
- 35 automated tests; `MODEL_MODE=fake` runs the whole pipeline with no model
  server

### Known limitations

| area | limitation |
|---|---|
| **Injection detection** | regex-based and advisory; a novel paraphrase can slip through. Never blocks on its own. |
| **Context** | `-c 16384` is the tested ceiling on 32 GB. Long documents are chunked; only top-scoring chunks reach the model. |
| **Scanned PDFs** | image-only PDFs extract no text. Standalone images are OCR'd; images *inside* a `.docx` or `.pdf` are not. |
| **SMTP** | the `.eml` artifact and the not-configured path are tested; delivery against a real mail server is not. |
| **Auth** | environment-variable identity shim, not real user authentication. `API_KEY` is a single shared secret. |
| **Approvals** | API only; no approval UI. |
| **Ungrounded answers** | pass verification by default; set `REQUIRE_EVIDENCE=true` to block. |

### Before production

- Set `API_KEY`; put the API behind TLS or a private network
- Replace the identity shim with real authentication and per-user authorization
- Move to PostgreSQL; establish backup and restore
- Add file-size, request-size and rate limits; scan uploads
- Pin an offline Python wheelhouse and document model checksums for air-gapped
  installs
- Add monitoring, structured logs, and a worker restart policy
- `llama-swap has no authentication` — keep it on loopback or behind a
  token-checking proxy

### Further reading

| document | contents |
|---|---|
| [LLAMA_SWAP_SETUP.md](LLAMA_SWAP_SETUP.md) | inference machine runbook: install, download, configure, troubleshoot |
| [CHANGES.md](CHANGES.md) | why each decision was made, with measurements; the honest record |
| [ARCHITECTURE.md](ARCHITECTURE.md) | lifecycle, security invariants, extension points |
| [TEAM_SETUP.md](TEAM_SETUP.md) | per-developer setup |
| [samples/README.md](samples/README.md) | what each test document demonstrates |
| [ELECTRON_INTEGRATION.md](ELECTRON_INTEGRATION.md) | desktop client integration notes |

---

## 10. Troubleshooting

| symptom | cause / fix |
|---|---|
| `MODEL_RETURNED_EMPTY_CONTENT` | the model spent its budget thinking, or memory pressure. Keep `LLM_ENABLE_THINKING=false`; check `llama-swap` logs for `Compute error`. |
| 500 `Compute error` from llama.cpp | out of memory. Lower `-c`, use a smaller quant, or do not co-resident large models. |
| `unknown model architecture: 'qwen35moe'` | llama.cpp too old — use a 2026 build. |
| Job fails with `model_error` | `LLM_BASE_URL` wrong or llama-swap not running. `curl localhost:8080/v1/models`. |
| Retrieval works but scores look lexical | the embedder is unreachable; `embedded` was 0 at ingest. Re-index after starting it. |
| Rerank ordering looks wrong | the rerank model must be a BERT-style cross-encoder. Qwen3-Reranker does not work through this endpoint. |
| SSE returns 401 in a browser | `EventSource` cannot send headers — proxy it, or use the `fetch()` reader in §4. |
| First request times out | a cold model load can take ~10 s (35B). Raise the client timeout. |
| `PATH_OUTSIDE_JOB_WORKSPACE` | an artifact name escaped the job directory — expected, this is the traversal guard. |
