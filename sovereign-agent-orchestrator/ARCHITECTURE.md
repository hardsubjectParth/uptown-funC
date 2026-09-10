# Architecture & Internals

> This file is retained as a compatibility pointer. The complete architecture, state machine, security invariants, API, deployment, testing, and roadmap are maintained in [SYSTEM_GUIDE.md](SYSTEM_GUIDE.md).

## End-to-end lifecycle
1. Electron uploads a file or references an attachment.
2. `POST /api/v1/agent/run` creates a durable job and immediately returns `job_id`.
3. Router classifies the task deterministically and selects a registry model.
4. Planner emits structured steps; no hidden chain-of-thought is exposed.
5. Each proposed tool is resolved through the registry and checked by deterministic policy.
6. Approved tools execute only inside the job workspace.
7. Results become observations.
8. Verifier evaluates task-specific completion and blocks delivery on failure.
9. Medium/high-risk actions can pause at `awaiting_approval` and resume only through the approval endpoint.
10. Artifacts are discovered inside `output/` and exposed through an API download endpoint.
11. Electron receives progress via SSE and renders the final answer/artifact.

## State machine
`queued → planning → acting → observing → verifying → delivering → done`

Alternative paths: `acting → awaiting_approval → acting`, `verifying → planning` when bounded retry is added, and terminal `failed/cancelled`.

## Security invariants
- The model never makes authorization decisions.
- Unknown tools are denied.
- Paths are canonicalized and must remain under `/workspace/<job_id>`.
- No arbitrary URL fetch tool exists.
- Artifact paths are never sent to Electron as host paths.
- Generated code must not receive host filesystem or Docker socket access; a container sandbox is the production extension point.

## Extension points
Model: Fake → Ollama → OpenAI-compatible vLLM/SGLang.
RAG: local fake/search tool → internal HTTP `/search` → PostgreSQL/pgvector.
Sandbox: current safe tool registry → ephemeral no-network container/gVisor/Firecracker.
Artifact: python-docx → python-pptx/openpyxl and templates.
Storage: SQLite dev → PostgreSQL production.
