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
| **Model families** | Qwen3.5 / Qwen3.6 for generation, Qwen3-Embedding for retrieval | Current generation as of Sept 2026; Qwen3.5+ is natively multimodal. No newer embedding/reranker line exists. |
| **Quantization** | Q4_K_M for generation; **Q8_0 for the 0.6B embedder** | Q4 on a 0.6B model measurably hurts retrieval quality; the size cost is negligible. |
| **coder model** | **Merged into `reasoner`** | Qwen3.6-35B-A3B is "agentic coding" capable; there is no separate Qwen3.6-Coder. |
| **reranker** | **Dropped for now** | `Qwen/Qwen3-Reranker-0.6B-GGUF` is gated on HF, and no rerank stage exists in the pipeline yet. Revisit when that work happens. |
| **Thinking mode** | **Off by default** (`LLM_ENABLE_THINKING=false`) | Qwen3.5/3.6 emit chain-of-thought into `reasoning_content` and fill `content` only afterwards. With thinking on they can spend the whole token budget reasoning and return an **empty** answer. See §4A. |
| **Classification (which task type)** | Regex for now; `router` model as a later upgrade | Instant, no model load. The `router` alias (Qwen3.5-2B) is reserved but not wired yet. |
| **GPU residency / eviction** | Handled by `llama-swap` groups, not Python | Simpler; the registry's `min_free_gpu_gb` is a hint for writing the llama-swap config, not runtime logic. |
| **Multilingual embeddings** | Deferred | English first; revisit for Indic-language documents. |

### Model lineup

| alias | model | quant | size | resident? | used for |
|---|---|---|---|---|---|
| `router` | Qwen3.5-2B | Q4_K_M | 1.28 GB | yes | classification / guardrail *(reserved, not wired)* |
| `embedder` | Qwen3-Embedding-0.6B | Q8_0 | 0.64 GB | yes | RAG embeddings (1024 dims) |
| `reasoner` | Qwen3.6-35B-A3B | **UD-Q4_K_M** | 22.13 GB + 0.90 mmproj | on demand | planning, summarization, analysis, approval notes, **coding**, general chat |
| `vision` | Qwen3.5-4B | Q4_K_M | 2.74 GB + 0.67 mmproj | on demand | OCR, scanned documents, drawing understanding |

Notes from actually fetching these:
- There is **no plain `Q4_K_M`** for Qwen3.6-35B-A3B — the options are `UD-Q4_K_M`
  (Unsloth Dynamic) or `MXFP4_MOE`. We use `UD-Q4_K_M`.
- **Qwen3.6-35B-A3B ships its own `mmproj`**, so the reasoner is vision-capable.
  The separate 4B `vision` model is therefore optional — see §4B.
- Every repo names its projector `mmproj-F16.gguf`, so models **must** live in
  per-model subdirectories or the files collide.

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

3. **`verifier.py` used a relative `workspace/` path**, so artifact verification
   looked in the wrong directory whenever `WORKSPACE_ROOT` was not the default.
   Verification runs *before* `job['artifacts']` is populated, so that filesystem
   check is what actually decides — the job would fail verification.
   → **Fixed:** `Verifier` now takes the `Workspace` and uses its root.

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

## 4A. Thinking models — a bug found during live bring-up

Qwen3.5 and Qwen3.6 are **reasoning ("thinking") models**. On an OpenAI-compatible
endpoint they return the chain of thought in a separate `reasoning_content` field
and fill `content` only after the thinking finishes. If the token budget runs out
mid-thought, the reply is:

```json
{"finish_reason": "length",
 "message": {"content": "", "reasoning_content": "Thinking Process: ..."}}
```

The first live call against Qwen3.5-2B hit exactly this: **`content` was empty**.
The original adapter read only `content` and had no `max_tokens`, so the
orchestrator would have generated a document with an **empty body and no error**.

Fixes:
- The adapter sends `chat_template_kwargs: {"enable_thinking": false}` unless
  thinking is explicitly requested (honoured by llama.cpp when `llama-server`
  runs with `--jinja`).
- It always sends `max_tokens` (default 2048) — previously nothing bounded generation.
- It returns `reasoning_content` and `finish_reason` alongside `content`.
- If `content` is empty **and** the model was truncated mid-thought, it raises
  `MODEL_TRUNCATED_WHILE_THINKING` instead of silently returning nothing.
- Request timeout raised 120 s → 300 s (a cold 35B load can exceed 120 s).

Knobs: `LLM_ENABLE_THINKING` (default `false`) and `LLM_MAX_TOKENS` (default 2048).
Turn thinking on for higher-quality reasoning, but raise the token budget with it.

## 4B. Open decision — who does OCR

Qwen3.6-35B-A3B ships its own `mmproj`, so `reasoner` is vision-capable and the
separate 4B `vision` model is optional:

| option | benefit | cost |
|---|---|---|
| OCR → `reasoner` | only one heavy model is ever loaded, so llama-swap **never swaps**; better OCR quality | keeps ~23 GB resident |
| OCR → `vision` (4B) | cheap, fast OCR | every alternation between OCR and reasoning pays a 20–60 s model reload |

Both are downloaded and both aliases are configured. The registry currently routes
`ocr` to `vision` (smaller, quicker to iterate on during bring-up). Flip the
`task_types` in `config/model_registry.yaml` to move it to `reasoner`.

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
| `app/models/adapter.py` | **new `OpenAICompatibleAdapter`** — per-call `model=<alias>`, hits `/v1/chat/completions`, parses `choices[0].message`, sends `Authorization: Bearer` when a key is set. Thinking-mode handling per §4A: `enable_thinking` toggle, `max_tokens`, returns `reasoning_content` + `finish_reason`, raises on truncated-empty. `FakeModel` kept. `OllamaAdapter` kept as legacy/reference. |
| `app/models/router.py` | **rewritten** — reads `model_registry.yaml`, regex `classify()` → `registry_task`, maps to `model_alias`, computes `fallback_alias`. Returns the richer routing dict. |
| `app/orchestrator/service.py` | `_call_model` passes the routed alias into `chat()` and retries once on `fallback_alias` (emits a `model_fallback` event). Document-provenance text in `_plan` is now provider-neutral (was Ollama-specific). |
| `app/rag/service.py` | embeddings → `POST /v1/embeddings` (`{"input": ...}`, reads `data[0].embedding`). Vision OCR fallback → OpenAI `image_url` data-URI format. Constructor now takes `llm_base_url`, alias names, `api_key`. |
| `app/config.py` | reformatted for readability. New settings: `MODEL_MODE` (`fake` \| `llamaswap`), `LLM_BASE_URL`, `LLM_API_KEY`, `MODEL_REGISTRY_PATH`, `EMBEDDING_MODEL_ALIAS`, `VISION_MODEL_ALIAS`, `LLM_ENABLE_THINKING`, `LLM_MAX_TOKENS`. Removed all `OLLAMA_*` settings. |
| `app/main.py` | builds `OpenAICompatibleAdapter` when `MODEL_MODE=llamaswap`; `ModelRouter(settings.model_registry_path)`; `RagService` gets the new args. |
| `cli.py` | same wiring as `main.py`. |
| `app/schemas/contracts.py` | `RoutingDecision` gained optional `registry_task`, `model_alias`, `fallback_alias`. |
| `.env.example` | `OLLAMA_*` → `MODEL_MODE` / `LLM_BASE_URL` / `LLM_API_KEY` / `MODEL_REGISTRY_PATH` / alias vars. |
| `docker-compose.yml` | env vars renamed; note added about pointing `LLM_BASE_URL` at a host-side llama-swap (`host.docker.internal`). |
| `.gitignore` | `workspace/` → `/workspace/` (stop ignoring the `app/workspace/` package); also ignores `config/llama-swap.yaml`, which holds machine-specific absolute model paths. |
| `tests/test_core.py` | router tests point at `config/model_registry.yaml` and assert `model_alias`; added a coding-routing test and a `WORKSPACE_ROOT` regression test for the verifier. |
| `app/verification/verifier.py` | took a hardcoded relative `./workspace` path, so artifact verification looked in the wrong place under a non-default `WORKSPACE_ROOT` (verification runs *before* `job['artifacts']` is populated, so the filesystem check is what decides). Now takes the `Workspace` and uses its root. |

### Files deleted

- `config/models.yaml`, `config/models.yaml.backup` — old Ollama/qwen registry, replaced by `config/model_registry.yaml`.
- `app/orchestrator/service.py.backup` — stray backup.

---

## 6. How to run

### Fake mode (no model server — used by tests and CI)
```bash
uv venv --python 3.12 && uv pip install -r requirements.txt
.venv/bin/python -m pytest -q                       # 11 passed
MODEL_MODE=fake WORKSPACE_ROOT=./workspace .venv/bin/python cli.py "…task…"
```

### Real mode (llama-swap + llama.cpp)
See **`LLAMA_SWAP_SETUP.md`**. Short version:
```bash
# on the inference machine
brew install llama.cpp            # + llama-swap RELEASE BINARY (not `go install`)
hf auth login                     # do this first: unauthenticated pulls fail/throttle
hf download …                     # 6 GGUFs into ~/models/<model>/ (~28 GB)
cp config/llama-swap.example.yaml config/llama-swap.yaml   # fix models_dir + paths
llama-swap -config config/llama-swap.yaml -validate        # check before starting
llama-swap -config config/llama-swap.yaml -listen :8080

# then the orchestrator
export MODEL_MODE=llamaswap LLM_BASE_URL=http://localhost:8080/v1 WORKSPACE_ROOT=./workspace
.venv/bin/python cli.py "summarize the inspection report and write an approval note"
```

---

## 7. Verification status

Software:
- ✅ `pytest` — 11 passed.
- ✅ `MODEL_MODE=fake` CLI run — produces a verified `.docx` artifact end-to-end.
- ✅ `app.main` imports in both `fake` and `llamaswap` mode.
- ✅ Router decisions spot-checked (summarization→reasoner, coding→reasoner, ocr→vision, general→reasoner).

Live bring-up on the M1 Max (in progress):
- ✅ llama.cpp `llama-server` build 10809 (Homebrew) — recent enough for Qwen3.5/3.6.
- ✅ llama-swap **v255** serving on `:8080`; `-validate` accepts our config.
- ✅ **Qwen3.5 architecture loads** in this llama.cpp build (the main compatibility risk).
- ✅ `/v1/embeddings` via alias `embedder` → 1024-dim vector in ~1.3 s.
- ✅ `/v1/chat/completions` via alias `router` → real generation through `OpenAICompatibleAdapter`.
- ⏳ 35B `reasoner` still downloading; full orchestrator run against it is the next step.

### Environment as installed (M1 Max, all native — no Docker)

Docker is deliberately not used for inference: Docker Desktop on macOS cannot
reach the Metal GPU, so llama.cpp in a container would be CPU-only.

```
llama.cpp     /opt/homebrew/bin/llama-server     (brew, build 10809)
llama-swap    ~/.local/bin/llama-swap            v255
models        ~/models/<model>/*.gguf
orchestrator  .venv (Python 3.12) in the repo
database      SQLite ./orchestrator.db
```

⚠️ `go install github.com/mostlygeek/llama-swap@latest` installs **v0.1.5**, not
the current release: llama-swap tags releases as `v255`, which Go cannot read as
semver for an unsuffixed module path, so it falls back to an ancient `v0.1.x`
tag. That build lacks `macros`, `groups`, and `ttl`. **Use the GitHub release
binary.** (A stale `~/go/bin/llama-swap` may still exist and shadow the good one
if PATH order changes.)

---

## 8. Not done yet / next steps

| item | notes |
|---|---|
| **Full live run against `reasoner`** | 35B download in progress; then run the orchestrator end-to-end and fix whatever breaks against real responses |
| **`reranker` stage** | no rerank step in the RAG pipeline yet (retrieval is cosine / lexical, top-k), and the official GGUF repo is gated |
| **`router` model for classification / guardrail** | classification is regex today; `router` (Qwen3.5-2B) is reserved for an LLM classify + prompt-injection check |
| **Coding workflow** | coding tasks route to `reasoner` but still run the doc pipeline (`search_documents` → `generate_docx`); no code-output plan branch |
| **Runtime GPU-gating** | `min_free_gpu_gb` in the registry is unused at runtime; residency is llama-swap's job |
| **Multilingual embeddings** | deferred |
| **Stale docs** | `README.md` and `team_work.md` still describe the Ollama setup and the old `config/models.yaml`; the root `README.md` describes a `podman compose` + vLLM-on-:8000 stack that does not exist in this repo |

---

## 9. Known gotchas

- **M1 Max 32 GB is the ceiling.** Residents (~2 GB) + Qwen3.6-35B-A3B Q4 (~23 GB
  with its projector) fits with a capped context. `vision` swaps with `reasoner` —
  expect a one-time load stall when alternating. Bigger GPU boxes are roomier.
- **Thinking models return empty `content`** if the token budget runs out during
  reasoning. See §4A — keep `LLM_ENABLE_THINKING=false` unless you also raise
  `LLM_MAX_TOKENS`.
- **Keep the API off port 8080** — that's llama-swap. Run `uvicorn` on 8081.
- **GGUF repo/filenames drift.** Always check the Hugging Face model card before
  running the `hf download` commands, and match `config/llama-swap.yaml` paths to
  `ls ~/models`. Notably there is no plain `Q4_K_M` for the 35B (it is `UD-Q4_K_M`).
- **Projector filenames collide.** Every repo calls its projector `mmproj-F16.gguf`;
  keep each model in its own subdirectory.
- **Log in to Hugging Face before large downloads.** Unauthenticated transfers are
  rate-limited and failed mid-file here with
  `CAS Client Error: ... error decoding response body`. `hf auth login` fixed it and
  raised throughput to ~14 MB/s.
- **llama.cpp must be a 2026 build** — Qwen3.5/3.6 use a hybrid-MoE architecture
  (`qwen35moe`) older builds don't recognise.
- **llama-swap has no auth.** On a shared network, put it behind a reverse proxy
  that checks a bearer token (`LLM_API_KEY`).
