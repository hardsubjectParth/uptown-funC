# Team Setup And Collaboration

> Setup, ownership, API, deployment, and operational guidance are consolidated into [SYSTEM_GUIDE.md](SYSTEM_GUIDE.md). This file is retained for historical collaboration notes.

## Recommended sharing model

Share the source through a private GitHub, GitLab, or Azure DevOps repository. Do not share the folder as a ZIP once development starts; Git gives the team branches, reviews, history, and conflict resolution.

Commit source code, migrations, tests, configuration templates, and documentation. Each developer should create their own `.env`, virtual environment, database volume, workspace, and Ollama model cache.

Never commit `.env`, API keys, `.venv/`, `orchestrator.db`, PostgreSQL data volumes, `workspace/` uploads, company documents, generated artifacts, logs, model weights, or Python caches. These paths are covered by `.gitignore`.

## First-time setup

```powershell
git clone <PRIVATE_REPOSITORY_URL>
cd sovereign-agent-orchestrator
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
pytest -q
```

Start the local API:

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
```

## System dependency: Tesseract (for image / scanned-document OCR)

```text
macOS:          brew install tesseract
Debian/Ubuntu:  sudo apt-get install -y tesseract-ocr
Windows:        install Tesseract OCR and put tesseract.exe on PATH
```

Without it, image and scanned-PDF OCR falls back to the local vision model
(`OCR_PREFER_VISION=true` forces the vision model even when Tesseract is present).

## Local Ollama setup

Install Ollama separately. Start it with these tuning flags -- benchmarked on a
32 GB M1 Max with `qwen3.6:27b`: flash attention alone is +25% generation speed
(6.1 -> 7.7 tok/s), and none of these cost measurable speed:

```bash
OLLAMA_FLASH_ATTENTION=1 OLLAMA_KV_CACHE_TYPE=q8_0 OLLAMA_NUM_PARALLEL=1 \
OLLAMA_MAX_LOADED_MODELS=1 ollama serve
```

Two ways to get the models:

**A. From the shared local GGUF set** (no re-download; models live in
`~/sovereign-agent/models/`):

```bash
MODELS_DIR=~/sovereign-agent/models ./scripts/ollama_setup.sh
```

This registers `sov-local`, `sov-vision`, `sov-coder` and pulls `nomic-embed-text`.

**B. From the Ollama registry** (edit `config/models.yaml` `model:` fields to match):

```powershell
ollama pull qwen2.5vl:3b
ollama pull qwen2.5-coder:7b
ollama pull nomic-embed-text
```

Use these settings in `.env`:

```text
MODEL_MODE=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=sov-local
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
OLLAMA_VISION_MODEL=sov-vision
LLM_ENABLE_THINKING=false
```

## Shared PostgreSQL/pgvector setup

Use Docker Compose for an integration environment:

```powershell
docker compose up --build
```

The PostgreSQL data volume is local to that machine. Do not put volume contents or company documents into Git.

## Authentication and tenant testing

```powershell
$headers = @{
  Authorization = 'Bearer local-development-key'
  'X-Tenant-ID' = 'company-a'
}
Invoke-RestMethod -Headers $headers -Uri 'http://localhost:8080/api/v1/ready'
```

Use different tenant headers to verify that jobs and indexed evidence remain isolated. In production, replace the shared API key with OIDC/JWT or mTLS.

## Git workflow

```powershell
git switch -c feat/document-ingestion
pytest -q
python -m compileall app cli.py
git diff
git add .
git diff --cached --stat
git commit -m "Describe the focused change"
git push -u origin feat/document-ingestion
```

Open a pull request and require review plus passing CI before merging. Review the staged diff for secrets, databases, uploads, and generated artifacts.

Suggested ownership: API/auth and tenant isolation, SQLAlchemy/migrations/pgvector, extraction/OCR/embeddings, orchestration/policy/tools, Electron, and deployment/secrets/backups should each have a named owner.

## CI minimum

```powershell
pip install -r requirements.txt
pytest -q
python -m compileall app cli.py
```

Integration CI should start PostgreSQL with pgvector, apply `migrations/tier/001_initial_pgvector.sql` and `migrations/core/001_operational.sql`, upload test fixtures, and verify tenant filtering, citation validation, queue recovery, and artifact download.

## Sharing this current checkout

This checkout currently has local changes and no configured remote. Review the staged diff before committing:

```powershell
git status --short
git remote -v
git add .
git diff --cached --stat
git commit -m "Add offline RAG and production persistence"
git remote add origin <PRIVATE_REPOSITORY_URL>
git push -u origin main
```

If the team repository already has a `main` branch, fetch it and push a feature branch for a pull request instead of pushing directly to `main`.
