# Inference machine runbook — llama-swap + llama.cpp

The orchestrator picks a **model alias** per task (`config/model_registry.yaml`)
and calls one OpenAI-compatible endpoint. `llama-swap` owns that endpoint and
loads/evicts the backing `llama.cpp` model for each alias on demand.

```
CLI / API ─▶ ModelRouter ─▶ alias ("reasoner" | "vision" | "router" | ...)
                                │
                                ▼
           OpenAICompatibleAdapter ─▶ http://<host>:8080/v1/chat/completions
                                │
                                ▼
                          llama-swap ──(loads on demand)──▶ llama-server + GGUF
```

## 0. Topology — pick one

| | where llama-swap runs | where the orchestrator runs | `LLM_BASE_URL` |
|---|---|---|---|
| **All-in-one** (dev / demo, M1 Max) | this machine | this machine | `http://localhost:8080/v1` |
| **Split** (GPU server) | the GPU box | laptop / app server | `http://<gpu-box-ip>:8080/v1` |

Sections 1–7 set up the inference machine. Section 8 runs the orchestrator.
Section 9 is the split-machine delta.

---

## 1. System prep

**Disk:** ~25–30 GB for the GGUFs. Everything the deployment owns lives under one
root so it is easy to find, back up, or move to another disk:

```bash
mkdir -p ~/sovereign-agent/{models,documents/inbox,artifacts}
```

```text
~/sovereign-agent/
├── models/            GGUF model files (~25 GB)
├── documents/inbox/   documents to index
└── artifacts/         generated outputs worth keeping
```

Only `models/` is required; the other two are conventions. The repo keeps its own
`workspace/` for per-job scratch and `samples/` for test fixtures.

**macOS (Apple Silicon):**
```bash
xcode-select --install        # if not already present
brew --version                 # need Homebrew
```

**Linux + NVIDIA:** install a recent driver + CUDA toolkit (`nvidia-smi` must work).

## 2. Install llama.cpp (provides `llama-server`)

**macOS:**
```bash
brew install llama.cpp
llama-server --version         # confirm; must be a 2026 build for Qwen3.5/3.6
```

**Linux + NVIDIA** — prebuilt binaries or build with CUDA:
```bash
# option A: release binaries
#   https://github.com/ggml-org/llama.cpp/releases  (cuda archive)
# option B: build
git clone https://github.com/ggml-org/llama.cpp && cd llama.cpp
cmake -B build -DGGML_CUDA=ON && cmake --build build -j --config Release
# add build/bin to PATH so `llama-server` resolves
```

## 3. Install llama-swap

Download the release binary for the OS/arch from
<https://github.com/mostlygeek/llama-swap/releases> (e.g. `llama-swap_*_darwin_arm64.tar.gz`,
`_linux_amd64.tar.gz`), then:

```bash
tar -xzf llama-swap_*_*.tar.gz
chmod +x llama-swap
mkdir -p ~/.local/bin && mv llama-swap ~/.local/bin/
llama-swap --version
```

⚠️ **Do not use `go install github.com/mostlygeek/llama-swap@latest`.** llama-swap
tags releases as `v255`, which Go cannot read as semver for an unsuffixed module
path, so it silently installs an ancient `v0.1.5` that lacks `macros`, `groups`
and `ttl`. Use the release binary. Check with `llama-swap --version`.

## 4. Install the Hugging Face CLI

```bash
pip install -U "huggingface_hub[cli]"
hf auth login     # do this BEFORE downloading
```

Log in even for public repos: unauthenticated transfers are rate-limited and
failed mid-file here with `CAS Client Error: ... error decoding response body`.
Throughput went from ~1 MB/s to ~14 MB/s after logging in.

## 5. Download the GGUFs

Lineup as measured on a 32 GB M1 Max. Qwen3.6-35B-A3B covers reasoning **and**
coding — there is no separate coder model. Every model here is multimodal except
the embedder and reranker.

| alias | model | quant | size | notes |
|---|---|---|---|---|
| `router` | Qwen3.5-2B | Q4_K_M | 1.28 GB | resident — optional LLM task classification |
| `embedder` | Qwen3-Embedding-0.6B | Q8_0 | 0.64 GB | resident — RAG embeddings (Q8, not Q4) |
| `reranker` | bge-reranker-v2-m3 | Q8_0 | 0.61 GB | resident — cross-encoder rerank |
| `reasoner-35b` | Qwen3.6-35B-A3B | **UD-IQ3_XXS** | 13.21 GB | on demand — the default reasoner |
| `reasoner-9b` | Qwen3.5-9B | Q4_K_M | 5.68 GB | on demand — benchmarked alternative |
| `vision` | Qwen3.5-4B | Q4_K_M | 2.74 GB | on demand — OCR / drawings |

⚠️ **Qwen3.6-35B-A3B at Q4 (22.13 GB) does not work on a 32 GB M1 Max.** It loads
and answers once, then llama.cpp returns 500 `Compute error` as soon as the
embedder loads beside it. Use `UD-IQ3_XXS`. There is no plain `Q4_K_M` for this
model — only `UD-Q4_K_M` and `MXFP4_MOE`.

Each model needs its **own subdirectory**: every repo names its projector
`mmproj-F16.gguf`, so a flat directory would overwrite them.

```bash
HF=~/sovereign-agent/models
hf download unsloth/Qwen3.5-2B-GGUF        Qwen3.5-2B-Q4_K_M.gguf          --local-dir $HF/qwen3.5-2b
hf download Qwen/Qwen3-Embedding-0.6B-GGUF Qwen3-Embedding-0.6B-Q8_0.gguf  --local-dir $HF/qwen3-embedding-0.6b
hf download gpustack/bge-reranker-v2-m3-GGUF bge-reranker-v2-m3-Q8_0.gguf  --local-dir $HF/bge-reranker-v2-m3
hf download unsloth/Qwen3.6-35B-A3B-GGUF   Qwen3.6-35B-A3B-UD-IQ3_XXS.gguf --local-dir $HF/qwen3.6-35b-a3b
hf download unsloth/Qwen3.6-35B-A3B-GGUF   mmproj-F16.gguf                 --local-dir $HF/qwen3.6-35b-a3b
hf download unsloth/Qwen3.5-4B-GGUF        Qwen3.5-4B-Q4_K_M.gguf          --local-dir $HF/qwen3.5-4b
hf download unsloth/Qwen3.5-4B-GGUF        mmproj-F16.gguf                 --local-dir $HF/qwen3.5-4b
# optional, only to re-run the reasoner benchmark:
hf download unsloth/Qwen3.5-9B-GGUF        Qwen3.5-9B-Q4_K_M.gguf          --local-dir $HF/qwen3.5-9b
hf download unsloth/Qwen3.5-9B-GGUF        mmproj-F16.gguf                 --local-dir $HF/qwen3.5-9b
```

⚠️ **Verify every repo name and filename on its Hugging Face model card first** —
GGUF publisher names and quant suffixes drift. Match the paths in
`config/llama-swap.yaml` to what actually lands (`ls -lh ~/sovereign-agent/models/*`).

## 6. Write the llama-swap config

```bash
cp config/llama-swap.example.yaml config/llama-swap.yaml
```

Edit `config/llama-swap.yaml`:
- set the `models_dir` macro to your absolute models path (`/Users/<you>/sovereign-agent/models`)
- match each `-m` / `--mmproj` filename to `ls ~/sovereign-agent/models/*`
- **Linux/NVIDIA:** keep `-ngl 99` (all layers on GPU). **CPU-only:** drop `-ngl`.
- `-c` (context) is capped deliberately — the models allow 262K but the KV cache
  would eat all RAM. Raise only if you have headroom.

## 7. Start llama-swap and verify

Foreground first (watch the logs):

```bash
llama-swap --config config/llama-swap.yaml --listen :8080
```

In another shell:

```bash
curl http://localhost:8080/v1/models
# request a model — llama-swap spawns llama-server for it on first call
curl http://localhost:8080/v1/chat/completions -H 'content-type: application/json' \
  -d '{"model":"reasoner-35b","messages":[{"role":"user","content":"ping"}],
       "chat_template_kwargs":{"enable_thinking":false}}'
# embeddings
curl http://localhost:8080/v1/embeddings -H 'content-type: application/json' \
  -d '{"model":"embedder","input":"fire extinguisher inspection interval"}'
# rerank
curl http://localhost:8080/v1/rerank -H 'content-type: application/json' \
  -d '{"model":"reranker","query":"overdue extinguisher",
       "documents":["cafeteria menu","FE-114 gauge in red band"]}'
```

First `reasoner-35b` call takes ~10 s (model load); subsequent calls are fast.
Note `enable_thinking:false` — without it Qwen3.5/3.6 can spend the whole token
budget reasoning and return empty `content`.
Once it works, run it backgrounded:

```bash
nohup llama-swap --config config/llama-swap.yaml --listen :8080 > ~/llama-swap.log 2>&1 &
```

(For a persistent service use `launchd` on macOS or a `systemd` unit on Linux.)

## 8. Run the orchestrator against it

From the repo, with the venv already created (`uv venv --python 3.12 && uv pip install -r requirements.txt`):

```bash
export MODEL_MODE=llamaswap
export LLM_BASE_URL=http://localhost:8080/v1
export MODEL_REGISTRY_PATH=config/model_registry.yaml
export WORKSPACE_ROOT=./workspace

# one-shot
.venv/bin/python cli.py "summarize the inspection report and write an approval note"

# or the API — keep it OFF :8080 (that's llama-swap)
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8081
```

End-to-end API check:

```bash
curl -F 'file=@some-report.pdf' http://127.0.0.1:8081/api/v1/files
curl -X POST http://127.0.0.1:8081/api/v1/agent/run -H 'content-type: application/json' \
  -d '{"task":"Read the report and draft an approval note with citations.",
       "attachments":[{"file_id":"<id-from-upload>"}]}'
curl http://127.0.0.1:8081/api/v1/agent/<job_id>          # poll
```

## 9. Split machine (inference on a separate box)

On the GPU box, in `config/llama-swap.yaml` change every model's
`--host 127.0.0.1` to `--host 0.0.0.0`, and start with `--listen 0.0.0.0:8080`.
Open port 8080 to the orchestrator host only (security group / `ufw`).

On the orchestrator host:

```bash
export LLM_BASE_URL=http://<gpu-box-ip>:8080/v1
export LLM_API_KEY=<shared-secret>     # optional; only if llama-swap is behind an auth proxy
```

llama-swap has no built-in auth — if the endpoint isn't on a private network, put
it behind a reverse proxy that checks a bearer token (the adapter sends
`Authorization: Bearer $LLM_API_KEY` when set).

## Memory note — M1 Max 32 GB

Measured, not estimated:

| configuration | wired |
|---|---|
| `reasoner-35b` (IQ3_XXS, `-c 16384`) alone | 18.2 GB |
| + `embedder` loaded alongside | 20.1 GB |
| + a 10,640-token prompt in flight | 20.1 GB |
| `reasoner-35b` at **Q4** + embedder | ✗ 500 `Compute error` |

The practical ceiling is around 22 GB. `-c` is charged **on top of** the weights,
so a large context is part of what breaks it — `-c 32768` contributed to the Q4
failure. `-c 16384` is the tested value; higher is untested here.

`vision` is in the heavy group and swaps with the reasoner, so alternating
between OCR and reasoning pays a model reload each time. Both reasoners are
multimodal, so you can drop `vision` and point OCR at the reasoner to avoid all
swapping.

## Not wired yet (future passes)

- `reranker` alias — no rerank stage in the RAG pipeline yet.
- `router` alias for classification / guardrail — classification is regex today.
- Runtime GPU-gating from `min_free_gpu_gb` — left to llama-swap groups.

## Troubleshooting

| symptom | fix |
|---|---|
| `unknown model architecture: 'qwen35moe'` | llama.cpp too old — update to a 2026 build |
| model loads then RAM pressure / swap | lower `-c`, or don't run `vision` + a reasoner concurrently |
| `curl /v1/models` OK but chat 500s | check `~/llama-swap.log` — usually a wrong `-m` path or missing `--mmproj` |
| orchestrator: `model_error` / connection refused | `LLM_BASE_URL` wrong, or llama-swap not running / not on that port |
| embeddings empty, retrieval still works | embedder call failing → RAG fell back to lexical; check the `embedder` model + `--embedding` flag |
| first call times out | raise the adapter timeout or `healthCheckTimeout`; a cold 35B load can exceed 60 s on cold disk |
| model replies with empty `content` | it spent the budget thinking — send `chat_template_kwargs:{"enable_thinking":false}` or raise `LLM_MAX_TOKENS` |
| rerank returns nonsense ordering | the model must be a BERT-style cross-encoder; Qwen3-Reranker does not work through this endpoint |
