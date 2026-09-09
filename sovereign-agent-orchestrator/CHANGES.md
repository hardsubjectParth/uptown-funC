# CHANGES — model-serving migration (Sept 2026)

A record of what changed in this migration, why each decision was made, what was
broken and got fixed, and what is still outstanding.

---

## 1. Goal of this work

Make the orchestrator run **multiple local LLMs** where **the agent picks the
right model per task** (not all at once), served through one endpoint. Then get
it running on real hardware (a MacBook Pro M1 Max 32 GB first; larger GPU
machines later).

Before this work the project was wired for **Ollama** with a single fixed model.
The routing logic that "chose" a model was cosmetic — it never affected which
model was actually called.

---

## 2. Decisions made (and why)

| Decision | Choice | Why |
|---|---|---|
| **Serving backend** | **llama.cpp behind `llama-swap`** (an OpenAI-compatible proxy that hot-loads/evicts models by alias) | We want N models, one at a time, auto-selected. `llama-swap` does exactly that. Also: Ollama cannot load Qwen3.5's vision projector (`qwen35moe` arch); llama.cpp can. |
| **API surface** | OpenAI-compatible `/v1` (`/v1/chat/completions`, `/v1/embeddings`) | One adapter then works with llama-swap, vLLM, LM Studio, etc. Swap runtimes per machine with one env var, no code change. |
| **Model families** | Qwen3.5 / Qwen3.6 for generation, Qwen3-Embedding / Qwen3-Reranker for retrieval | Current generation as of Sept 2026; Qwen3.5+ is natively multimodal. No newer embedding/reranker line exists. |
| **Quantization** | Q4_K_M for generation; **Q8_0 for the 0.6B embedder & reranker** | Q4 on a 0.6B model measurably hurts retrieval quality; the size cost is negligible. |
| **coder model** | **Merged into `reasoner`** | Qwen3.6-35B-A3B is "agentic coding" capable; there is no separate Qwen3.6-Coder. |
| **Classification (which task type)** | Regex for now; `router` model as a later upgrade | Instant, no model load. The `router` alias (Qwen3.5-2B) is reserved but not wired yet. |
| **GPU residency / eviction** | Handled by `llama-swap` groups, not Python | Simpler; the registry's `min_free_gpu_gb` is a hint for writing the llama-swap config, not runtime logic. |
| **Multilingual embeddings** | Deferred | English first; revisit for Indic-language documents. |

### Model lineup

| alias | model | quant | resident? | used for |
|---|---|---|---|---|
| `router` | Qwen3.5-2B | Q4_K_M | yes | classification / guardrail *(reserved, not wired)* |
| `embedder` | Qwen3-Embedding-0.6B | Q8_0 | yes | RAG embeddings |
| `reranker` | Qwen3-Reranker-0.6B | Q8_0 | yes | RAG rerank *(reserved, not wired)* |
| `reasoner` | Qwen3.6-35B-A3B | Q4_K_M | on demand | planning, summarization, analysis, approval notes, **coding**, general chat |
| `vision` | Qwen3.5-4B *(or 9B)* + mmproj | Q4_K_M | on demand | OCR, scanned documents, drawing understanding |

---

## 3. Blockers found (project did not run at all) — fixed

1. **`app/workspace/manager.py` was missing.** The `Workspace` class is imported
   by `app/main.py` and `cli.py` and used across the codebase, but the file was
   never committed — `.gitignore` had `workspace/`, which also matched the
   `app/workspace/` package. Nothing imported.
   → **Recreated** the file (+ `__init__.py`) and **changed `.gitignore`** to
   `/workspace/` (anchored to repo root) so only the runtime job directory is
   ignored.

2. **Python version.** Project requires 3.12; the machine had 3.9.
   → Use a 3.12 virtualenv (`uv venv --python 3.12`).

3. **`verifier.py` uses a relative `workspace/` path** — works only when run from
   the repo root with the default `WORKSPACE_ROOT`. Left as-is (works for the
   current run modes); noted here as a latent bug.

---

## 4. How model selection works now

### Before
```
router.route(task)  ->  picks a model id from config/models.yaml   (never used)
main.py             ->  builds ONE OllamaAdapter from $OLLAMA_MODEL (always this one)
orchestrator        ->  self.model.chat(messages)                   (no model arg)
```

### After
```
router.route(task)
  ├─ classify(task)         regex -> fine-grained task ("coding", "ocr", "summarization", ...)
  ├─ look up model_registry.yaml by task -> model_alias ("reasoner" / "vision" / ...)
  └─ returns { task_type (workflow), registry_task, model_alias, fallback_alias, ... }

orchestrator._call_model
  └─ self.model.chat(messages, model=routing["model_alias"])
       └─ on failure, retry once with routing["fallback_alias"]

OpenAICompatibleAdapter.chat(messages, model=<alias>)
  └─ POST $LLM_BASE_URL/v1/chat/completions  { "model": "<alias>", "messages": [...] }
       └─ llama-swap loads/evicts the llama.cpp model for that alias
```

Two vocabularies, kept deliberately separate:
- **`registry_task`** — fine-grained, decides *which model* (`coding`, `ocr`,
  `analysis`, `planning`, `approval_note`, `summarization`, `general`).
- **`task_type`** — coarse workflow, decides *which plan* the orchestrator runs
  (`general`, `document_workflow`, `coding`, `multimodal`). The router returns both.

---

## 5. File-by-file changes

### New files

| file | purpose |
|---|---|
| `app/workspace/manager.py`, `app/workspace/__init__.py` | the missing `Workspace` class (per-job dirs + path-traversal guard, absolute-rooted) |
| `config/model_registry.yaml` | the Router's decision table: `model_alias` ↔ `task_types`. Replaces `config/models.yaml`. |
| `config/llama-swap.example.yaml` | template llama-swap config: alias → `llama-server` command + GGUF path, with resident/heavy groups |
| `LLAMA_SWAP_SETUP.md` | full inference-machine runbook (install, download, configure, run, troubleshoot) |
| `CHANGES.md` | this document |

### Modified files

| file | change |
|---|---|
| `app/models/adapter.py` | **new `OpenAICompatibleAdapter`** — per-call `model=<alias>`, hits `/v1/chat/completions`, parses `choices[0].message`, sends `Authorization: Bearer` when a key is set. `FakeModel` kept. `OllamaAdapter` kept as legacy/reference. |
| `app/models/router.py` | **rewritten** — reads `model_registry.yaml`, regex `classify()` → `registry_task`, maps to `model_alias`, computes `fallback_alias`. Returns the richer routing dict. |
| `app/orchestrator/service.py` | `_call_model` passes the routed alias into `chat()` and retries once on `fallback_alias` (emits a `model_fallback` event). Document-provenance text in `_plan` is now provider-neutral (was Ollama-specific). |
| `app/rag/service.py` | embeddings → `POST /v1/embeddings` (`{"input": ...}`, reads `data[0].embedding`). Vision OCR fallback → OpenAI `image_url` data-URI format. Constructor now takes `llm_base_url`, alias names, `api_key`. |
| `app/config.py` | reformatted for readability. New settings: `MODEL_MODE` (`fake` \| `llamaswap`), `LLM_BASE_URL`, `LLM_API_KEY`, `MODEL_REGISTRY_PATH`, `EMBEDDING_MODEL_ALIAS`, `VISION_MODEL_ALIAS`. Removed all `OLLAMA_*` settings. |
| `app/main.py` | builds `OpenAICompatibleAdapter` when `MODEL_MODE=llamaswap`; `ModelRouter(settings.model_registry_path)`; `RagService` gets the new args. |
| `cli.py` | same wiring as `main.py`. |
| `app/schemas/contracts.py` | `RoutingDecision` gained optional `registry_task`, `model_alias`, `fallback_alias`. |
| `.env.example` | `OLLAMA_*` → `MODEL_MODE` / `LLM_BASE_URL` / `LLM_API_KEY` / `MODEL_REGISTRY_PATH` / alias vars. |
| `docker-compose.yml` | env vars renamed; note added about pointing `LLM_BASE_URL` at a host-side llama-swap (`host.docker.internal`). |
| `.gitignore` | `workspace/` → `/workspace/` (stop ignoring the `app/workspace/` package). |
| `tests/test_core.py` | router tests point at `config/model_registry.yaml` and assert `model_alias`; added a coding-routing test. |

### Files now stale (safe to delete — not done yet)

- `config/models.yaml`, `config/models.yaml.backup` — old Ollama/qwen registry, no longer read.
- `app/orchestrator/service.py.backup` — stray backup.

---

## 6. How to run

### Fake mode (no model server — used by tests and CI)
```bash
uv venv --python 3.12 && uv pip install -r requirements.txt
.venv/bin/python -m pytest -q                       # 10 passed
MODEL_MODE=fake WORKSPACE_ROOT=./workspace .venv/bin/python cli.py "…task…"
```

### Real mode (llama-swap + llama.cpp)
See **`LLAMA_SWAP_SETUP.md`**. Short version:
```bash
# on the inference machine
brew install llama.cpp                              # + download llama-swap binary
hf download …                                       # 6 GGUFs into ~/models (~25 GB)
cp config/llama-swap.example.yaml config/llama-swap.yaml   # fix the paths
llama-swap --config config/llama-swap.yaml --listen :8080

# then the orchestrator
export MODEL_MODE=llamaswap LLM_BASE_URL=http://localhost:8080/v1 WORKSPACE_ROOT=./workspace
.venv/bin/python cli.py "summarize the inspection report and write an approval note"
```

---

## 7. Verification status

- ✅ `pytest` — 10 passed.
- ✅ `MODEL_MODE=fake` CLI run — produces a verified `.docx` artifact end-to-end.
- ✅ `app.main` imports in both `fake` and `llamaswap` mode.
- ✅ Router decisions spot-checked (summarization→reasoner, coding→reasoner, ocr→vision, general→reasoner).
- ⛔ **Not yet tested against a live llama-swap** — no GGUFs / llama-swap on the dev machine. This is the next real step.

---

## 8. Not done yet / next steps

| item | notes |
|---|---|
| **Live test against llama-swap** | download models on a target machine, start llama-swap, run the orchestrator, fix whatever breaks against real responses |
| **`reranker` stage** | `reranker` alias exists; there is no rerank step in the RAG pipeline yet (retrieval is cosine / lexical, top-k) |
| **`router` model for classification / guardrail** | classification is regex today; `router` (Qwen3.5-2B) is reserved for an LLM classify + prompt-injection check |
| **Coding workflow** | coding tasks route to `reasoner` but still run the doc pipeline (`search_documents` → `generate_docx`); no code-output plan branch |
| **Runtime GPU-gating** | `min_free_gpu_gb` in the registry is unused at runtime; residency is llama-swap's job |
| **Multilingual embeddings** | deferred |
| **Delete stale files** | `config/models.yaml*`, `service.py.backup` |
| **`verifier.py` relative path** | should honor `WORKSPACE_ROOT` |

---

## 9. Known gotchas

- **M1 Max 32 GB is the ceiling.** Residents (~5 GB) + Qwen3.6-35B-A3B Q4 (~20 GB)
  fits with a capped context. `vision` swaps with `reasoner` — expect a one-time
  load stall when alternating. Bigger GPU boxes are where this is comfortable.
- **Keep the API off port 8080** — that's llama-swap. Run `uvicorn` on 8081.
- **GGUF repo/filenames drift.** Always check the Hugging Face model card before
  running the `hf download` commands, and match `config/llama-swap.yaml` paths to
  `ls ~/models`.
- **llama.cpp must be a 2026 build** — Qwen3.5/3.6 use a hybrid-MoE architecture
  (`qwen35moe`) older builds don't recognise.
- **llama-swap has no auth.** On a shared network, put it behind a reverse proxy
  that checks a bearer token (`LLM_API_KEY`).
