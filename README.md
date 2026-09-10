# uptown-funC

SIH-2026 submission — a sovereign (fully local, air-gappable) agent orchestrator
for document workflows.

Everything lives in [`sovereign-agent-orchestrator/`](sovereign-agent-orchestrator/).

## What it does

Accepts a task, routes it to the right local model, retrieves supporting
documents, runs a policy-controlled tool plan, verifies the result, and delivers
a cited artifact. No cloud calls — inference and retrieval both run on the
machine.

```
API / CLI ─▶ Router ─▶ model alias ─▶ llama-swap ─▶ llama.cpp (local GGUF)
                │                          │
                ├─ RAG retrieval ──────────┘
                ├─ policy-controlled tools
                ├─ verification gate
                └─ artifact (.docx with evidence citations, or source files)
```

## Quick start

```bash
cd sovereign-agent-orchestrator
uv venv --python 3.12 && uv pip install -r requirements.txt

# Works with no model server at all (deterministic stub, used by the tests):
MODEL_MODE=fake .venv/bin/python cli.py "summarize the inspection report"
.venv/bin/python -m pytest -q
```

For real local models, see
**[sovereign-agent-orchestrator/LLAMA_SWAP_SETUP.md](sovereign-agent-orchestrator/LLAMA_SWAP_SETUP.md)** —
install llama.cpp + llama-swap, download the GGUFs, start the server, run the API.

## Where things live

The repo holds code and fixtures; everything the deployment owns lives under one
root outside it, so models and data are easy to find, back up, or relocate:

```text
uptown-funC/                       this repo
└── sovereign-agent-orchestrator/
    ├── app/                       application code
    ├── config/                    model registry + llama-swap config
    ├── samples/                   test documents (see samples/README.md)
    └── workspace/                 per-job scratch and artifacts (gitignored)

~/sovereign-agent/                 deployment data (outside the repo)
├── models/                        GGUF model files (~25 GB)
├── documents/inbox/               documents to index
└── artifacts/                     generated outputs worth keeping
```

`config/llama-swap.yaml` points at `~/sovereign-agent/models` and is gitignored
because it holds absolute paths; `config/llama-swap.example.yaml` is the shared
template.

## Documentation

| file | what it covers |
|---|---|
| [`sovereign-agent-orchestrator/README.md`](sovereign-agent-orchestrator/README.md) | full guide: install, API, RAG, deployment |
| [`sovereign-agent-orchestrator/LLAMA_SWAP_SETUP.md`](sovereign-agent-orchestrator/LLAMA_SWAP_SETUP.md) | inference-machine runbook |
| [`sovereign-agent-orchestrator/CHANGES.md`](sovereign-agent-orchestrator/CHANGES.md) | migration record: decisions, measurements, open items |
| [`sovereign-agent-orchestrator/samples/README.md`](sovereign-agent-orchestrator/samples/README.md) | what each test document is for |
| [`sovereign-agent-orchestrator/ARCHITECTURE.md`](sovereign-agent-orchestrator/ARCHITECTURE.md) | lifecycle and security invariants |
| [`ENTERPRISE_RAG_ROADMAP.md`](ENTERPRISE_RAG_ROADMAP.md) | longer-term build plan |

## Models

Served locally through `llama-swap`, which loads and evicts them on demand so
several models can be available without running them all at once.

| alias | model | role |
|---|---|---|
| `reasoner-35b` | Qwen3.6-35B-A3B (IQ3_XXS) | planning, summarization, approval notes, coding |
| `embedder` | Qwen3-Embedding-0.6B | RAG embeddings |
| `vision` | Qwen3.5-4B | OCR, scanned documents |
| `router` | Qwen3.5-2B | task classification (optional) |
| `reasoner-9b` | Qwen3.5-9B | benchmarked alternative reasoner |

Storage is SQLite by default; PostgreSQL + pgvector is supported via
`DATABASE_URL` with the migrations in `sovereign-agent-orchestrator/migrations/`.
