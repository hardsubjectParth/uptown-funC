# Team Setup And Collaboration

## Recommended sharing model

Share the source through a private GitHub, GitLab, or Azure DevOps repository. Do not share the folder as a ZIP once development starts; Git gives the team branches, reviews, history, and conflict resolution.

Commit source code, migrations, tests, configuration templates, and documentation. Each developer should create their own `.env`, virtual environment, database volume, workspace, `config/llama-swap.yaml`, and local GGUF model directory.

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

## Local model setup

Each developer installs llama.cpp and llama-swap and downloads the GGUF models
once. The full procedure, including the `hf download` commands, is in
[LLAMA_SWAP_SETUP.md](LLAMA_SWAP_SETUP.md).

```bash
brew install llama.cpp          # macOS; see the runbook for Linux
# plus the llama-swap release binary (NOT `go install` - see the runbook)
hf auth login                   # unauthenticated pulls throttle and fail
```

Copy the config template and fix the model paths for your machine:

```bash
cp config/llama-swap.example.yaml config/llama-swap.yaml
llama-swap -config config/llama-swap.yaml -validate
llama-swap -config config/llama-swap.yaml -listen :8080
```

`config/llama-swap.yaml` is gitignored because it holds absolute paths; the
`.example` is the shared version.

Use these settings in `.env`:

```text
MODEL_MODE=llamaswap
LLM_BASE_URL=http://localhost:8080/v1
MODEL_REGISTRY_PATH=config/model_registry.yaml
EMBEDDING_MODEL_ALIAS=embedder
VISION_MODEL_ALIAS=vision
```

Run the API on a different port than llama-swap:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8081
```

No model server? `MODEL_MODE=fake` runs the whole pipeline with a deterministic
stub - that is what the test suite uses.

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

Integration CI should start PostgreSQL with pgvector, apply `migrations/001_initial_pgvector.sql` and `migrations/002_operational.sql`, upload test fixtures, and verify tenant filtering, citation validation, queue recovery, and artifact download.

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
