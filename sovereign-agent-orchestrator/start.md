# Starting the project manually

Everything was stopped at the end of the last session (API, frontend dev
server, and `ollama serve`). This is the full sequence to bring it back up
from a cold machine, in order.

## 0. One-time setup (skip if already done)

```bash
cd sovereign-agent-orchestrator

# Backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Frontend
cd frontend
npm install
cd ..
```

Backend `.env` — this checkout has no `.env` yet, only `.env.example`. Create
one:

```bash
cp .env.example .env
```

Then edit `.env` and set, at minimum:

```bash
MODEL_MODE=ollama
DEV_AUTH_ENABLED=true
DEV_ADMIN_PASSWORD=<pick-something>
JWT_SECRET=<32+ random characters — dev login 503s below that>
```

(`AUTH_MODE=jwt` and the other `DEV_*` values already default sensibly in
`.env.example`; `MODEL_MODE=fake` is the file's default and needs no model
server at all — see the fake-mode section below if that's all you need.)

Frontend `.env` (already present in this checkout, `frontend/.env`):

```bash
VITE_API_BASE_URL=http://localhost:8080/api/v1
```

## 1. Start Ollama

```bash
OLLAMA_FLASH_ATTENTION=1 OLLAMA_KV_CACHE_TYPE=q8_0 OLLAMA_NUM_PARALLEL=1 \
OLLAMA_MAX_LOADED_MODELS=1 ollama serve
```

Run this in its own terminal tab (it stays in the foreground), or backgrounded:

```bash
OLLAMA_FLASH_ATTENTION=1 OLLAMA_KV_CACHE_TYPE=q8_0 OLLAMA_NUM_PARALLEL=1 \
OLLAMA_MAX_LOADED_MODELS=1 nohup ollama serve > /tmp/ollama.log 2>&1 &
```

Confirm the models used by `.env.example`'s recommended set are pulled:

```bash
ollama list
```

Expect `qwen3.6:27b`, `qwen3-vl:8b`, `bge-m3`. If missing:

```bash
ollama pull qwen3.6:27b   # reasoner + coder + calc + docs + general (~17 GB)
ollama pull qwen3-vl:8b   # vision: scans, screenshots, drawings, handwriting (~6 GB)
ollama pull bge-m3        # embeddings, multilingual (~1.2 GB)
```

⚠️ Real-model runs are heavy — a prior run with a larger model froze this
Mac. `qwen3.6:27b` at these settings has run fine this session, but keep an
eye on memory (`Activity Monitor` → wired memory, or `sysctl vm.swapusage`)
on anything bigger, and prefer `MODEL_MODE=fake` (below) for quick dashboard
checks that don't need real model output.

## 2. Start the backend API

⚠️ **The app does not auto-load `.env`** — there's no `python-dotenv` wired
in on this branch, so a `.env` file sitting on disk is silently ignored
unless you actually export its values into the shell first. From
`sovereign-agent-orchestrator/`:

```bash
set -a
. ./.env
set +a
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
```

(`set -a` / `set +a` makes every variable `source`d in between exported
automatically — plain `source .env` alone will not pass them to uvicorn.)

Verify:

```bash
curl -s http://127.0.0.1:8080/api/v1/health
curl -s http://127.0.0.1:8080/api/v1/ready | python3 -m json.tool
```

`/ready` reports the active model, embedding model, and vision model, and
whether each backing service is actually reachable.

### Fake mode (no Ollama needed)

For quick dashboard/UI checks without a model server, set `MODEL_MODE=fake`
in `.env` (its default) instead of `ollama`, and skip step 1 entirely — the
whole pipeline runs on deterministic stub responses.

## 3. Start the frontend

In a separate terminal, from `sovereign-agent-orchestrator/frontend/`:

```bash
npm run dev
```

Vite serves on `http://localhost:5173` by default.

## 4. Open and log in

Go to **http://localhost:5173**. On the login screen:

- **Test account**: `Admin` (or `Higher`/`Lower`)
- **Password**: whatever you set as `DEV_ADMIN_PASSWORD` (etc.) in `.env`

This dev-login screen only works while `DEV_AUTH_ENABLED=true` — it's not
present/usable in a production deployment.

## Stopping everything

```bash
pkill -f "uvicorn app.main:app"
pkill -f "node .*/vite"
pkill -f "ollama serve"
```

(`pkill -f "vite --host"` only matches if you started it with an explicit
`--host` flag — plain `npm run dev` won't have that in its command line, so
match on the vite binary path instead.)

Or just `Ctrl+C` each foreground terminal if you didn't background them.

## Quick reference — what's running, where

| Service | Command | Port | Depends on |
|---|---|---|---|
| Ollama | `ollama serve` | 11434 | nothing |
| Backend API | `uvicorn app.main:app` | 8080 | Ollama (unless `MODEL_MODE=fake`) |
| Frontend | `npm run dev` (vite) | 5173 | Backend API |

Start in that order; stop in reverse (or just `pkill` all three, order
doesn't matter there).
