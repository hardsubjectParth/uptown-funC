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

**Disk:** ~25–30 GB for the GGUFs. Pick a directory you control:

```bash
mkdir -p ~/models
```

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

(Go toolchain alternative: `go install github.com/mostlygeek/llama-swap@latest`.)

## 4. Install the Hugging Face CLI

```bash
pip install -U "huggingface_hub[cli]"
# hf auth login        # only if a model repo is gated (Qwen GGUFs generally are not)
```

## 5. Download the GGUFs

Lineup (Sept 2026). Qwen3.6-35B-A3B covers reasoning **and** coding — there is no
separate coder model. Ollama can't load Qwen3.5 vision (`qwen35moe` mmproj);
llama.cpp can, via `--mmproj`.

| alias | model | quant | notes |
|---|---|---|---|
| `router` | Qwen3.5-2B | Q4_K_M | resident (classification/guardrail — not wired yet) |
| `embedder` | Qwen3-Embedding-0.6B | Q8_0 | resident — RAG embeddings (Q8, not Q4) |
| `reranker` | Qwen3-Reranker-0.6B | Q8_0 | resident — RAG rerank (not wired yet) |
| `reasoner` | **Qwen3.6-35B-A3B** | Q4_K_M | on demand — planning, summary, analysis, approval notes, coding |
| `vision` | Qwen3.5-4B *(or 9B)* | Q4_K_M | on demand — OCR / drawings; needs `mmproj` |

```bash
HF=~/models
hf download unsloth/Qwen3.5-2B-GGUF          Qwen3.5-2B-Q4_K_M.gguf         --local-dir $HF
hf download Qwen/Qwen3-Embedding-0.6B-GGUF   Qwen3-Embedding-0.6B-Q8_0.gguf --local-dir $HF
hf download Qwen/Qwen3-Reranker-0.6B-GGUF    Qwen3-Reranker-0.6B-Q8_0.gguf  --local-dir $HF
hf download unsloth/Qwen3.6-35B-A3B-GGUF     Qwen3.6-35B-A3B-Q4_K_M.gguf    --local-dir $HF
hf download unsloth/Qwen3.5-4B-GGUF          Qwen3.5-4B-Q4_K_M.gguf         --local-dir $HF
hf download unsloth/Qwen3.5-4B-GGUF          mmproj-Qwen3.5-4B-f16.gguf     --local-dir $HF
```

⚠️ **Verify every repo name and filename on its Hugging Face model card first** —
GGUF publisher names and quant suffixes drift, and the vision `mmproj` filename
varies. Fix the paths in `config/llama-swap.yaml` to match what actually lands in
`~/models` (`ls -lh ~/models`).

## 6. Write the llama-swap config

```bash
cp config/llama-swap.example.yaml config/llama-swap.yaml
```

Edit `config/llama-swap.yaml`:
- set the `models_dir` macro to your absolute models path (`/Users/<you>/models`)
- match each `-m` / `--mmproj` filename to `ls ~/models`
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
  -d '{"model":"reasoner","messages":[{"role":"user","content":"ping"}]}'
# embeddings
curl http://localhost:8080/v1/embeddings -H 'content-type: application/json' \
  -d '{"model":"embedder","input":"fire extinguisher inspection interval"}'
```

First `reasoner` call takes 20–60 s (model load); subsequent calls are fast.
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

Residents (`router` 2B + `embedder` + `reranker`) ≈ 5 GB. Qwen3.6-35B-A3B at Q4 ≈
20–21 GB → one heavy model fits alongside the residents. `vision` is in the heavy
group and swaps with `reasoner`; the first vision call after a reasoning call (or
vice-versa) pays a one-time load stall. That's the ceiling on this machine —
bigger GPU boxes can raise `-c` and pull `vision` out of the heavy group.

## Not wired yet (future passes)

- `reranker` alias — no rerank stage in the RAG pipeline yet.
- `router` alias for classification / guardrail — classification is regex today.
- Runtime GPU-gating from `min_free_gpu_gb` — left to llama-swap groups.
- Coding tasks route to `reasoner` but still run the docx workflow.

## Troubleshooting

| symptom | fix |
|---|---|
| `unknown model architecture: 'qwen35moe'` | llama.cpp too old — update to a 2026 build |
| model loads then RAM pressure / swap | lower `-c`, or don't run `vision` + `reasoner` concurrently |
| `curl /v1/models` OK but chat 500s | check `~/llama-swap.log` — usually a wrong `-m` path or missing `--mmproj` |
| orchestrator: `model_error` / connection refused | `LLM_BASE_URL` wrong, or llama-swap not running / not on that port |
| embeddings empty, retrieval still works | embedder call failing → RAG fell back to lexical; check the `embedder` model + `--embedding` flag |
| first call times out | raise the adapter timeout or `healthCheckTimeout`; 35B first load can exceed 60 s on cold disk |
