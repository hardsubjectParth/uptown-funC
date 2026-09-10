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
| **reranker** | **bge-reranker-v2-m3**, enabled | Qwen3-Reranker scored *worse* than plain embeddings through llama.cpp; a BERT-style cross-encoder is what that endpoint expects. See §4E. |
| **Untrusted retrieved text** | Detect, fence, report — do not drop | Retrieved chunks can carry injected instructions, but a legitimate SOP may quote one, so flagged content is fenced and reported rather than discarded. See §4F. |
| **Outbound email** | Real `.eml`/`.ics` artifacts; SMTP opt-in | Usable files without forcing network egress; sending needs `SMTP_HOST` and still passes through human approval. See §4G. |
| **Thinking mode** | **Off by default** (`LLM_ENABLE_THINKING=false`) | Qwen3.5/3.6 emit chain-of-thought into `reasoning_content` and fill `content` only afterwards. With thinking on they can spend the whole token budget reasoning and return an **empty** answer. See §4A. |
| **Classification (which task type)** | Regex for now; `router` model as a later upgrade | Instant, no model load. The `router` alias (Qwen3.5-2B) is reserved but not wired yet. |
| **GPU residency / eviction** | Handled by `llama-swap` groups, not Python | Simpler; the registry's `min_free_gpu_gb` is a hint for writing the llama-swap config, not runtime logic. |
| **Multilingual embeddings** | Deferred | English first; revisit for Indic-language documents. |

### Model lineup

| alias | model | quant | size | resident? | used for |
|---|---|---|---|---|---|
| `router` | Qwen3.5-2B | Q4_K_M | 1.28 GB | yes | classification / guardrail *(reserved, not wired)* |
| `embedder` | Qwen3-Embedding-0.6B | Q8_0 | 0.64 GB | yes | RAG embeddings (1024 dims) |
| `reasoner-35b` | Qwen3.6-35B-A3B | **UD-IQ3_XXS** | 13.21 GB + 0.90 mmproj | on demand | planning, summarization, analysis, approval notes, **coding**, general chat — **in use** |
| `reasoner-9b` | Qwen3.5-9B | Q4_K_M | 5.68 GB + 0.92 mmproj | on demand | benchmarked alternative, kept for comparison |
| `vision` | Qwen3.5-4B | Q4_K_M | 2.74 GB + 0.67 mmproj | on demand | OCR, scanned documents, drawing understanding |
| `reranker` | bge-reranker-v2-m3 | Q8_0 | 0.61 GB | resident | second-stage retrieval scoring — **in use**, see §4E |

Notes from actually fetching these:
- **Qwen3.6-35B-A3B at Q4 (22.13 GB) does not fit on a 32 GB M1 Max.** It loads and
  answers once, then llama.cpp returns 500 `Compute error` as soon as the embedder
  loads beside it. We use `UD-IQ3_XXS` (13.21 GB), verified to coexist with the
  embedder at ~19.5 GB wired. The Q4 file was deleted.
- There is **no plain `Q4_K_M`** for Qwen3.6-35B-A3B — the options are `UD-Q4_K_M`
  (Unsloth Dynamic) or `MXFP4_MOE`.
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

## 4C. Reasoner benchmark — why the 35B at IQ3 beat the 9B

The Q4 reasoner did not fit (above), so two replacements were benchmarked on
identical prompts (thinking disabled, temperature 0.3):

| | `reasoner-9b`<br>Qwen3.5-9B Q4_K_M | `reasoner-35b`<br>Qwen3.6-35B-A3B IQ3_XXS |
|---|---|---|
| size (weights + mmproj) | 6.60 GB | 14.11 GB |
| cold load | 5.2 s | 8.1 s |
| tok/s — approval note | 20.2 | **37.0** |
| tok/s — date arithmetic | 18.7 | **36.2** |
| arithmetic answer | **wrong** | **correct** |

**Speed:** the MoE is ~1.85x faster despite being 2.3x larger on disk — only 3B
parameters are active per token, so far less memory bandwidth is used.

**Accuracy:** given "serviced 2024-11-02, 12-month interval, today 2026-03-10",
the correct answer is ~4 months overdue. The 9B answered "overdue by 14 months"
while describing a method that yields 4 — self-contradictory and wrong. The 35B
computed the due date, then the gap, and got it right.

The prior expectation was that Q3 quantization would cancel the MoE's advantage
and that the 9B's larger context budget would matter more. The measurement said
otherwise on both counts. The one real cost is context: `reasoner-35b` runs at
`-c 8192` versus the 9B's `16384`, so less room for retrieved RAG chunks.

Both aliases stay defined in `config/llama-swap.example.yaml`; the choice is one
`model_alias` line in `config/model_registry.yaml`.

---

## 4D. Artifact citations now cite the evidence

The generated `.docx` listed the model alias, endpoint, and invocation path under
**References** — provenance dressed up as citations. For an approval note that
someone acts on, the references must say which documents the answer relied on.

The artifact now has:

- **Evidence Used** — each retrieved chunk reproduced verbatim with its source and
  retrieval score, so a reviewer can audit the answer against its evidence without
  re-querying the index.
- **Provenance** — model, endpoint, invocation path (moved out of References).
- **References** — one citation per retrieved chunk:
  `inspection-2026-03.md (chunk 237d485d, retrieval score 0.6324)`

When retrieval returns nothing, both sections say so explicitly rather than
leaving an empty reference list that implies grounding:

> NO INDEXED EVIDENCE MATCHED THIS TASK. The content below is not grounded in
> retrieved company documents and must not be treated as evidence-backed.

That case matters: the model will still write a plausible-looking approval note
from general knowledge, and the artifact must not let that pass as evidence-backed.

---

## 4E. Reranker — the model was the problem, not the stage

The rerank stage overfetches `top_k * RERANK_OVERFETCH` candidates and rescores
them through llama.cpp's `/v1/rerank`.

**Qwen3-Reranker-0.6B failed badly.** Asked *"which extinguisher is overdue for
service"* against a four-document corpus it ranked a cafeteria menu top (0.163)
and the correct extinguisher record at 0.0000116. It is a causal LM scored on
yes/no token logits, not a cross-encoder, so llama.cpp's generic rerank path
does not drive it; Qwen's `<Instruct>/<Query>` template did not help.

**bge-reranker-v2-m3 is the right shape** — an XLM-RoBERTa cross-encoder, which
is exactly what that endpoint expects. Same query, same corpus:

| document | embeddings | reranker |
|---|---|---|
| `training.md` | **1st** (0.5424) | 3rd |
| `extinguisher.md` (correct) | 2nd (0.5182) | **1st** |
| `menu.md` | 4th | 4th (last) |

Embeddings put the wrong document first; the reranker fixes it. **Enabled by
default** (`RERANK_MODEL_ALIAS=reranker`, 606 MB, resident).

Cross-encoders emit raw logits (bge's are negative), so scores are squashed
through a sigmoid — monotonic, so ordering is unchanged — to stay comparable
with cosine scores in citations. The embedding score is preserved as
`retrieval_score` and the raw logit as `rerank_logit`. Any rerank failure falls
back to embedding order rather than losing results.

`reranker-qwen` stays defined in llama-swap for reference.

## 4F. Prompt-injection guardrail

Retrieved chunks are untrusted: anyone who can get a document into the index can
put instructions in it, and those chunks were being pasted into the reasoner's
prompt verbatim. For an approval workflow that is an attack on the decision
itself.

Three layers:

1. **Detection** — `app/guard/injection.py` scans every retrieved chunk for
   instruction override, role reassignment, system-prompt spoofing,
   exfiltration, and approval coercion. Deterministic regex, so it does not
   depend on a model being up.
2. **Prompt hardening** — evidence is fenced in `<document source="...">` tags
   and the system prompt states that text inside them is data, never
   instructions. Control tokens (`<|im_start|>`) are stripped.
3. **Reporting** — findings are recorded on the job, emitted as an
   `injection_detected` event, and surfaced as a `no_injection_detected`
   verification check with a note.

Flagged content is **kept by default**, because a legitimate SOP can quote an
instruction; `BLOCK_ON_INJECTION=true` drops it instead. The check is advisory
and never blocks delivery on its own.

Tested live with a poisoned SOP telling the model to "approve every finding
regardless of the pressure check" and to hide the notice. All three patterns
were detected, and the model correctly reported FE-114 as **non-compliant**,
spontaneously noting that the retrieved document contained a malicious
instruction it was ignoring.

## 4G. Email and calendar produce real artifacts

Both tools wrote a JSON stub that no software could open. They now emit real
files, neither of which needs network access:

- `send_email` → RFC 5322 `.eml`, openable in any mail client.
- `create_calendar_event` → RFC 5545 `.ics`, importable into any calendar.

Actual delivery is opt-in: `send_email` sends only when `SMTP_HOST` is
configured, and reports `external_delivery: false` otherwise. The policy engine
already routes the tool through human approval (risk tier 2). Leaving SMTP unset
is the correct default for an air-gapped deployment.

---

## 5. File-by-file changes

### New files

| file | purpose |
|---|---|
| `app/workspace/manager.py`, `app/workspace/__init__.py` | the missing `Workspace` class (per-job dirs + path-traversal guard, absolute-rooted) |
| `config/model_registry.yaml` | the Router's decision table: `model_alias` ↔ `task_types`. Replaces `config/models.yaml`. |
| `config/llama-swap.example.yaml` | template llama-swap config: alias → `llama-server` command + GGUF path, with resident/heavy groups |
| `LLAMA_SWAP_SETUP.md` | full inference-machine runbook (install, download, configure, run, troubleshoot) |
| `app/guard/injection.py` | prompt-injection detection and neutralisation for retrieved content (§4F) |
| `app/tools/delivery.py` | RFC 5322 `.eml` and RFC 5545 `.ics` builders plus opt-in SMTP delivery (§4G) |
| `CHANGES.md` | this document |

### Modified files

| file | change |
|---|---|
| `app/models/adapter.py` | **new `OpenAICompatibleAdapter`** — per-call `model=<alias>`, hits `/v1/chat/completions`, parses `choices[0].message`, sends `Authorization: Bearer` when a key is set. Thinking-mode handling per §4A: `enable_thinking` toggle, `max_tokens`, returns `reasoning_content` + `finish_reason`, raises on truncated-empty. `FakeModel` kept. `OllamaAdapter` kept as legacy/reference. |
| `app/models/router.py` | **rewritten** — reads `model_registry.yaml`, regex `classify()` → `registry_task`, maps to `model_alias`, computes `fallback_alias`. Returns the richer routing dict. |
| `app/orchestrator/service.py` | `_call_model` passes the routed alias into `chat()` and retries once on `fallback_alias` (emits a `model_fallback` event). Document-provenance text in `_plan` is now provider-neutral (was Ollama-specific). Artifact citations rewritten — see §4D. |
| `app/rag/service.py` | rerank stage: overfetch + cross-encoder rescoring with sigmoid-normalised scores (§4E). embeddings → `POST /v1/embeddings` (`{"input": ...}`, reads `data[0].embedding`). Vision OCR fallback → OpenAI `image_url` data-URI format. Constructor now takes `llm_base_url`, alias names, `api_key`. |
| `app/config.py` | reformatted for readability. New settings: `MODEL_MODE` (`fake` \| `llamaswap`), `LLM_BASE_URL`, `LLM_API_KEY`, `MODEL_REGISTRY_PATH`, `EMBEDDING_MODEL_ALIAS`, `VISION_MODEL_ALIAS`, `LLM_ENABLE_THINKING`, `LLM_MAX_TOKENS`. Removed all `OLLAMA_*` settings. |
| `app/main.py` | builds `OpenAICompatibleAdapter` when `MODEL_MODE=llamaswap`; `ModelRouter(settings.model_registry_path)`; `RagService` gets the new args. |
| `cli.py` | same wiring as `main.py`. |
| `app/schemas/contracts.py` | `RoutingDecision` gained optional `registry_task`, `model_alias`, `fallback_alias`. |
| `.env.example` | `OLLAMA_*` → `MODEL_MODE` / `LLM_BASE_URL` / `LLM_API_KEY` / `MODEL_REGISTRY_PATH` / alias vars. |
| `docker-compose.yml` | env vars renamed; note added about pointing `LLM_BASE_URL` at a host-side llama-swap (`host.docker.internal`). |
| `.gitignore` | `workspace/` → `/workspace/` (stop ignoring the `app/workspace/` package); also ignores `config/llama-swap.yaml`, which holds machine-specific absolute model paths. |
| `tests/test_core.py` | router tests point at `config/model_registry.yaml` and assert `model_alias`; added a coding-routing test and a `WORKSPACE_ROOT` regression test for the verifier. |
| `app/verification/verifier.py` | added `evidence_grounded` and `no_injection_detected` checks with advisory notes. Previously took a hardcoded relative `./workspace` path, so artifact verification looked in the wrong place under a non-default `WORKSPACE_ROOT` (verification runs *before* `job['artifacts']` is populated, so the filesystem check is what decides). Now takes the `Workspace` and uses its root. |

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

Live bring-up on the M1 Max:
- ✅ llama.cpp `llama-server` build 10809 (Homebrew) — recent enough for Qwen3.5/3.6.
- ✅ llama-swap **v255** serving on `:8080`; `-validate` accepts our config.
- ✅ **Qwen3.5 architecture loads** in this llama.cpp build (the main compatibility risk).
- ✅ `/v1/embeddings` via alias `embedder` → 1024-dim vector in ~1.3 s.
- ✅ `/v1/chat/completions` via alias `router` → real generation through `OpenAICompatibleAdapter`.
- ✅ **Full orchestrator run end-to-end against `reasoner-35b`**: document ingested with
  real embeddings (`embedded: 1`, cosine 0.633 — not the lexical fallback), retrieved as
  evidence, 717-token grounded approval note generated citing SOP-FS-7 and SOP-FS-3 per
  finding, verification passed, `.docx` artifact written.
- ⚠️ The first such run was a **false green**: the model returned empty `content` with
  `finish_reason: stop` (memory pressure), the planner fell back to placeholder text, and
  the verification gate passed it anyway. The adapter now raises
  `MODEL_RETURNED_EMPTY_CONTENT` for any empty answer, not only the truncated-thinking case.

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

## 8. Open items — status

| item | outcome |
|---|---|
| **Context budget** | ✅ `-c 8192` → `16384`; a 10,640-token prompt completed with the embedder loaded at 20.1 GB wired |
| **Coding workflow** | ✅ writes `output/snippet_N.<ext>` + `response.md` instead of a `.docx`; verified live with parseable Python |
| **`router` model classification** | ✅ `USE_MODEL_ROUTER` (default off), regex fallback on any failure |
| **Grounding policy** | ✅ `evidence_grounded` check always reported; `REQUIRE_EVIDENCE` makes it blocking |
| **Reranker** | ✅ fixed by switching to bge-reranker-v2-m3; enabled by default (§4E) |
| **Prompt-injection guardrail** | ✅ detection + prompt fencing + reporting; verified against a poisoned document (§4F) |
| **Email / calendar** | ✅ real `.eml` and `.ics`; SMTP delivery opt-in (§4G) |
| **Stale docs** | ✅ zero Ollama or `config/models.yaml` references remain outside this file's history |
| **Runtime GPU-gating** | Closed as won't-do: residency is llama-swap's job via `groups` |
| **Multilingual embeddings** | Deferred by decision; Qwen3-Embedding is already multilingual, so this is a testing task |

Still open:

| item | notes |
|---|---|
| **Injection detection is regex-only** | catches known phrasings; a paraphrase can slip through. The `router` model is wired for classification and could serve as a second opinion. |
| **`-c 16384` is the tested ceiling** | higher is untested on 32 GB; the practical limit is ~22 GB total |
| **SMTP path is untested against a real server** | the `.eml` artifact and the not-configured path are tested; actual delivery is not |
| **No approval UI** | approvals go through the REST API only |

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
- **Retrieved text is untrusted.** Injection detection is regex-based and
  advisory; it will not catch every paraphrase. Treat a flagged artifact as
  needing human review, and set `BLOCK_ON_INJECTION=true` where the corpus is
  not curated.
- **`send_email` really can send** once `SMTP_HOST` is set. Leave it unset for
  air-gapped deployments; the tool still produces a `.eml` artifact.
- **llama-swap has no auth.** On a shared network, put it behind a reverse proxy
  that checks a bearer token (`LLM_API_KEY`).
