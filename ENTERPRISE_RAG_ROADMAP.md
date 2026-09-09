# Enterprise Offline RAG Roadmap

> This roadmap is now consolidated into [sovereign-agent-orchestrator/SYSTEM_GUIDE.md](sovereign-agent-orchestrator/SYSTEM_GUIDE.md). The master guide distinguishes implemented capabilities, verified capabilities, and remaining production gates.

## Current baseline

The repository already provides a useful single-server vertical slice:

- Local ingestion for TXT, Markdown, PDF, DOCX, CSV, XLSX, XLSM, and common images.
- Chunking, durable SQLite/PostgreSQL storage, optional Ollama embeddings, and lexical fallback.
- Tenant and clearance metadata filters on API search and orchestrator retrieval.
- FastAPI upload/search endpoints, durable jobs, SSE events, approvals, audit records, and workspace traversal protection.
- DOCX/JSON workbook reports and a local CLI workflow.
- Deterministic policy and verification gates.

This is a strong offline MVP. Enterprise readiness means making correctness, isolation, operations, and integrations explicit and measurable.

## Build phases

### Phase 1: production single-server foundation

1. Add file size, page count, row count, timeout, and disk quota limits.
2. Add MIME/content validation, archive-bomb protection, malware scanning hook, and upload checksum handling.
3. Add source/document listing, delete, re-index, retention, and failed-ingestion status APIs.
4. Add structured citations with document ID, page/sheet, chunk ID, and quoted evidence.
5. Add retrieval evaluation fixtures: hit rate, recall@k, MRR, citation validity, and no-answer behavior.
6. Add health/readiness checks for database, storage, embedding model, OCR, and queue worker.
7. Add structured JSON logs, correlation IDs, metrics, backups, restore tests, and graceful worker restart.

### Phase 2: trustworthy enterprise RAG

1. Enforce tenant, clearance, department, project, and document ACL filters at the storage query boundary.
2. Add hybrid retrieval: lexical plus vector, reciprocal-rank fusion, metadata filters, and reranking.
3. Add parent-child chunks, page/table/image provenance, deduplication, and versioned re-indexing.
4. Add query rewriting, multi-query retrieval, contextual compression, and a strict answer-with-citations contract.
5. Add PII detection/redaction, retention policies, legal hold, deletion propagation, and audit exports.
6. Add prompt-injection detection for retrieved content and treat documents as untrusted data.

### Phase 3: enterprise operations

1. PostgreSQL/pgvector as the multi-user production store; SQLite remains the single-server mode.
2. Redis or a durable broker for concurrent workers, retries, dead-letter queues, and idempotency keys.
3. SSO/OIDC, RBAC/ABAC, service accounts, secret rotation, TLS, rate limits, quotas, and admin controls.
4. Object storage for originals and artifacts, immutable audit storage, encryption at rest, and backup lifecycle management.
5. OpenTelemetry traces, Prometheus metrics, alerting, dashboards, and incident runbooks.

### Phase 4: remote enterprise tools

Implement connectors through one typed adapter boundary. Every connector needs scoped credentials, read/write separation, rate limits, audit events, dry-run mode, idempotency, and approval policy.

- Read-only SQL and warehouse queries.
- SharePoint, OneDrive, S3, Google Drive, and network file shares.
- Jira, ServiceNow, Linear, and GitHub issues.
- Slack, Teams, email, and calendar.
- ERP/CRM and internal REST APIs.
- Web search or URL fetch only in a controlled egress service with allowlists and content sanitization.
- Sandboxed Python/Node execution only in an ephemeral no-network container or microVM.

## Model lineup

The active default is `qwen2.5vl:3b`, which is suitable for a small local server and image-aware document workflows. Optional profiles are defined in `config/models.yaml` and should be enabled only after the model is pulled locally.

| Tier | Suggested local model | Best use | Approximate memory | Tradeoff |
|---|---|---|---:|---|
| Fast | `qwen3:4b` | routing, classification, short summaries | 4 GB | fastest, less depth |
| Balanced | `qwen2.5vl:3b` | default single-server RAG and vision | 4 GB | good general quality |
| Quality | `qwen3:14b` | long reports, difficult synthesis | 10 GB | slower, stronger reasoning |
| Vision | `qwen2.5vl:7b` | scans, tables, diagrams, images | 8 GB | better multimodal accuracy |
| Coding | `qwen2.5-coder:7b` | code analysis and generation | 8 GB | specialized rather than general |
| Reasoning | `qwen3:30b-a3b` | complex planning and adjudication | 20 GB | highest local cost |
| Embedding | `nomic-embed-text` | English semantic retrieval | 1 GB | compact and fast |
| Multilingual embedding | `bge-m3` | multilingual and cross-language search | 3 GB | slower, broader coverage |

Model selection should be based on measured latency, VRAM/RAM, retrieval quality, answer quality, and failure rate on the team's evaluation set, not model name alone.

## Tool rollout policy

The initial safe tool set is knowledge search, workspace reads, controlled writes, and artifact generation. The complete catalog is in `config/tools.yaml`. Recommended order:

1. `ingest_document`, `list_sources`, `export_report`, `spreadsheet_profile`, and `extract_tables`.
2. `redact_pii`, `ocr_document`, and read-only SQL.
3. Enterprise read connectors: drives, SharePoint, GitHub, Jira, Slack, and internal APIs.
4. Approved writes: tickets, calendar events, messages, and email with human approval.
5. Sandboxed code execution and controlled external search only after isolation and egress controls are proven.

## Definition of done

Call the system enterprise-ready only when it can demonstrate: zero cross-tenant retrieval in automated tests; reproducible citations; evaluated retrieval metrics; bounded resource usage; restart and restore success; complete audit trails; SSO/RBAC; approval and idempotency for writes; prompt-injection defenses; and a documented model/data retention policy.