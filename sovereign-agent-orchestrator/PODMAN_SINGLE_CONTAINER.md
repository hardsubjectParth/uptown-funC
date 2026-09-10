# Single-container Podman deployment

This deployment runs one container containing PostgreSQL 17 with pgvector, four logical databases, Ollama, a Python 3.12 environment managed by uv, Tesseract OCR, the FastAPI API, and the durable worker.

The logical RAG databases retain clearance-tier boundaries. This is a single-node appliance: PostgreSQL, Ollama, API, and worker share one failure domain. Use the existing multi-service compose deployment when separate process or service scaling is required.

## Windows PowerShell

From `sovereign-agent-orchestrator`:

```powershell
Copy-Item podman-single.env.example podman-single.env
# Edit podman-single.env and set POSTGRES_PASSWORD and JWT_SECRET.
.\podman-single.ps1 -Action build
.\podman-single.ps1 -Action start
.\podman-single.ps1 -Action logs
```

The API is bound only to localhost:

```powershell
Invoke-RestMethod http://127.0.0.1:8080/api/v1/health
Invoke-RestMethod http://127.0.0.1:8080/api/v1/ready
.\podman-single.ps1 -Action doctor
```

## Models and air-gap operation

Set `OLLAMA_PULL_ON_START=true` only during a preparation phase with approved network access. Then run `.\podman-single.ps1 -Action pull-models`. For the air-gapped phase, set it back to `false`, retain the `sovereign-ollama` volume, and block outbound network access.

## Persistent volumes

```text
sovereign-pgdata
sovereign-workspace
sovereign-ollama
```

Back up PostgreSQL with `pg_dumpall` or `pg_dump` from inside the container and export the workspace and Ollama model volume according to the site's backup policy. Do not delete these volumes during routine upgrades.