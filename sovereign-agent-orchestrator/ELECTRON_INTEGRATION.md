# Sovereign AI Workbench — Electron Integration Specification
## REST + SSE Contract for the Agent Orchestrator

> **Scope:** This document is the contract between an Electron desktop client and the Python/FastAPI Agent Orchestrator.

> The Electron application must not need to understand LangGraph, Ollama, PostgreSQL, pgvector, MCP internals, sandbox implementation, or RAG internals. Those are backend concerns.

---

# 1. Integration Goal

Electron should provide the user experience:

```text
Chat / Task Input
Attachments
Progress
Plan
Tool activity
Verification
Human approval
Artifacts
Final answer
Audit timeline
```

The backend provides:

```text
routing
planning
tool execution
security
verification
state
artifacts
audit
```

The frontend and backend communicate through:

```text
REST/JSON
+
Server-Sent Events (SSE)
```

MVP may use REST polling only.

---

# 2. Base URL

Development:

```text
http://localhost:8080
```

Recommended API prefix:

```text
/api/v1
```

Therefore:

```text
POST http://localhost:8080/api/v1/agent/run
```

Production should use a configurable base URL.

Electron must read it from configuration.

Never hard-code:

```text
localhost
```

into UI logic.

---

# 3. API Principles

The API must be:

- versioned
- typed
- deterministic
- backward-compatible
- safe to retry where possible
- independent of LangGraph
- independent of the selected model

The UI should rely on enums and structured fields.

Never parse free-form text to determine state.

---

# 4. Start Agent Job

Endpoint:

```http
POST /api/v1/agent/run
```

Content-Type:

```text
application/json
```

Request:

```json
{
  "task": "Read the Pump P-101 inspection report and draft an approval note citing the relevant SOP.",
  "user_context": {
    "user_id": "raj.mehta",
    "role": "inspection_engineer",
    "department": "inspection",
    "clearance": "internal",
    "project": "plant-a"
  },
  "attachments": [
    {
      "name": "pump_p101_report.pdf",
      "path": "input/pump_p101_report.pdf",
      "mime_type": "application/pdf"
    }
  ],
  "options": {
    "max_iterations": 3
  }
}
```

Response should be fast:

```json
{
  "job_id": "b3e1e9b0-...",
  "status": "queued"
}
```

Do not hold the connection open for the whole agent run.

---

# 5. User Context

Electron should send context supplied by the authenticated desktop session.

Schema:

```json
{
  "user_id": "raj.mehta",
  "role": "inspection_engineer",
  "department": "inspection",
  "clearance": "internal",
  "project": "plant-a"
}
```

Future fields can include:

```text
groups
site
plant
business_unit
locale
```

Important:

The backend must treat this context as authorization input.

Do not trust model-generated values.

---

# 6. Attachments

Attachments should be represented as metadata references.

Recommended:

```json
{
  "name": "report.pdf",
  "path": "input/report.pdf",
  "mime_type": "application/pdf"
}
```

For production, preferably upload through a dedicated API:

```text
POST /api/v1/files
```

Then the task references:

```json
{
  "file_id": "file-123"
}
```

This prevents Electron from needing to know backend filesystem paths.

---

# 7. Recommended Upload Flow

For a large file:

```text
Electron
   |
   | multipart upload
   v
POST /api/v1/files
   |
   v
backend stores file
   |
   v
returns file_id
```

Response:

```json
{
  "file_id": "file-123",
  "name": "report.pdf",
  "mime_type": "application/pdf",
  "size_bytes": 1248123
}
```

Then:

```http
POST /api/v1/agent/run
```

with:

```json
{
  "attachments": [
    {
      "file_id": "file-123"
    }
  ]
}
```

This is the recommended production contract.

---

# 8. Poll Job

Endpoint:

```http
GET /api/v1/agent/{job_id}
```

Response:

```json
{
  "job_id": "b3e1...",
  "status": "acting",
  "routing": {
    "task_type": "document_workflow",
    "model_id": "hermes-agent",
    "confidence": 0.93,
    "reason": "Requires multi-step document reasoning and local tools."
  },
  "plan": [],
  "tool_calls": [],
  "observations": [],
  "verification": null,
  "requires_human_approval": false,
  "artifacts": [],
  "final_answer": null,
  "error": null
}
```

Electron can poll until:

```text
done
failed
awaiting_approval
cancelled
```

---

# 9. Status Enum

The frontend must support:

```text
queued
planning
acting
observing
verifying
awaiting_approval
delivering
failed
done
cancelled
```

Suggested UI labels:

| Backend | UI |
|---|---|
| queued | Queued |
| planning | Planning |
| acting | Working |
| observing | Reviewing tool output |
| verifying | Verifying |
| awaiting_approval | Awaiting approval |
| delivering | Preparing files |
| done | Completed |
| failed | Failed |
| cancelled | Cancelled |

---

# 10. Routing Object

The UI may show the routing decision.

Example:

```json
{
  "task_type": "coding",
  "model_id": "coding-local",
  "confidence": 0.96,
  "reason": "Task requires code generation and execution.",
  "fallback_model_id": "hermes-agent"
}
```

Display:

```text
Model
Qwen Coder 7B

Reason
Coding task with executable tests

Confidence
96%
```

The UI must not allow users to spoof the selected model through display text.

---

# 11. Plan Object

Example:

```json
{
  "step_id": "s1",
  "description": "Search for the Pump P-101 inspection report",
  "tool": "search_documents",
  "tool_args": {
    "query": "Pump P-101 vibration inspection"
  },
  "status": "done"
}
```

The frontend can display a timeline:

```text
✓ Search inspection report
✓ Search applicable SOP
⟳ Generate approval note
○ Verify result
```

Do not display hidden chain-of-thought.

Only show the structured task plan.

---

# 12. Tool Call Object

Example:

```json
{
  "call_id": "call-10",
  "tool": "search_documents",
  "risk_tier": 0,
  "policy_decision": "allow",
  "success": true,
  "started_at": "...",
  "finished_at": "...",
  "result_summary": "Found 5 relevant chunks."
}
```

UI:

```text
SEARCH_DOCUMENTS
Policy: ALLOWED
Result: 5 documents found
```

---

# 13. Policy Object

Every tool action should expose:

```json
{
  "risk_tier": 1,
  "policy_decision": "allow"
}
```

Possible decisions:

```text
allow
deny
require_approval
```

For denied calls:

```json
{
  "risk_tier": 4,
  "policy_decision": "deny",
  "reason_code": "TOOL_NOT_PERMITTED"
}
```

The UI should distinguish:

```text
Policy blocked
```

from:

```text
Tool execution failed
```

These are different conditions.

---

# 14. Verification Object

Example:

```json
{
  "passed": true,
  "checks": {
    "plan_completed": true,
    "citations_present": true,
    "citation_sources_valid": true,
    "artifacts_exist": true,
    "code_tests_passed": true,
    "no_unhandled_denials": true
  },
  "notes": []
}
```

UI:

```text
Verification PASSED

✓ Plan completed
✓ Citations present
✓ Sources valid
✓ Artifact exists
✓ No unhandled policy denials
```

For a failed verification:

```json
{
  "passed": false,
  "checks": {
    "plan_completed": true,
    "citations_present": false,
    "citation_sources_valid": false,
    "artifacts_exist": true
  },
  "notes": [
    "A cited source could not be matched to retrieved evidence."
  ]
}
```

Electron should show:

```text
Verification failed — agent is retrying
```

not immediately present the answer as final.

---

# 15. Retry Display

A critical UI behavior:

```text
Attempt 1
Verification failed

Retrying...
```

Then:

```text
Attempt 2
Verification passed
```

This is important for demonstrating genuine agentic iteration.

---

# 16. Human Approval

When status becomes:

```text
awaiting_approval
```

response:

```json
{
  "job_id": "job-123",
  "status": "awaiting_approval",
  "requires_human_approval": true,
  "approval": {
    "risk_tier": 2,
    "reason": "This action requires human review before execution."
  }
}
```

Electron should present:

```text
Human approval required

Action:
Generate approval note

Risk:
Medium

Reason:
This action is configured to require reviewer confirmation.

[Approve] [Reject]
```

Do not make approval a chat message.

It must be a structured action.

---

# 17. Approve

Endpoint:

```http
POST /api/v1/agent/{job_id}/approve
```

Request:

```json
{
  "approved": true,
  "reviewer_user_id": "plant.manager"
}
```

Response:

```json
{
  "job_id": "job-123",
  "status": "acting"
}
```

For rejection:

```json
{
  "approved": false,
  "reviewer_user_id": "plant.manager"
}
```

Expected:

```json
{
  "job_id": "job-123",
  "status": "failed"
}
```

No deferred action may execute after rejection.

---

# 18. Cancel

Endpoint:

```http
POST /api/v1/agent/{job_id}/cancel
```

Response:

```json
{
  "job_id": "job-123",
  "status": "cancelled"
}
```

Electron should show:

```text
Task cancelled
```

The backend must terminate active sandbox execution.

---

# 19. Artifact List

Response:

```json
{
  "artifacts": [
    {
      "artifact_id": "art-123",
      "name": "approval_note.docx",
      "type": "docx",
      "size_bytes": 48231,
      "download_url": "/api/v1/agent/job-123/artifacts/art-123"
    }
  ]
}
```

The Electron client should never construct filesystem paths.

Use:

```text
download_url
```

---

# 20. Download Artifact

Endpoint:

```http
GET /api/v1/agent/{job_id}/artifacts/{artifact_id}
```

Response:

```text
application/vnd.openxmlformats-officedocument.wordprocessingml.document
```

The Electron client can save it using a native file dialog.

---

# 21. Final Answer

Example:

```json
{
  "final_answer": "Draft approval note created using the inspection report and vibration SOP. Verification passed."
}
```

Keep the final answer concise.

The detailed structured information is represented elsewhere:

```text
routing
plan
tool_calls
verification
artifacts
```

This allows Electron to present a clean chat result without losing auditability.

---

# 22. SSE Events

Recommended endpoint:

```http
GET /api/v1/agent/{job_id}/events
Accept: text/event-stream
```

Example:

```text
event: model_selected
data: {"model_id":"hermes-agent","confidence":0.93}

event: plan_created
data: {"steps":3}

event: step_started
data: {"step_id":"s1"}

event: tool_started
data: {"tool":"search_documents"}

event: tool_completed
data: {"tool":"search_documents","success":true}

event: verification_started
data: {}

event: verification_passed
data: {"checks":4}

event: artifact_created
data: {"artifact_id":"art-123"}

event: job_completed
data: {"status":"done"}
```

---

# 23. Event Reconnect

Electron may disconnect temporarily.

The client should:

```text
1. reconnect SSE
2. fetch current GET /agent/{id}
3. resume event stream
```

The GET endpoint is the source of truth.

SSE is an optimization for responsiveness, not the authoritative state store.

---

# 24. Event Types

Required event types:

```text
job_created
model_selected
plan_created
step_started
step_completed
tool_started
tool_completed
observation_created
verification_started
verification_failed
verification_passed
approval_required
approval_granted
approval_denied
artifact_created
job_completed
job_failed
job_cancelled
```

---

# 25. Electron State Machine

Recommended renderer state:

```text
IDLE
 |
 v
SUBMITTING
 |
 v
RUNNING
 |
 +--> APPROVAL_REQUIRED
 |       |
 |       +--> APPROVING
 |       |
 |       +--> REJECTED
 |
 v
COMPLETED
 |
 +--> FAILED
 +--> CANCELLED
```

Use a single state store.

Do not scatter job state across components.

---

# 26. Suggested Electron Data Types

TypeScript:

```ts
export type JobStatus =
  | "queued"
  | "planning"
  | "acting"
  | "observing"
  | "verifying"
  | "awaiting_approval"
  | "delivering"
  | "failed"
  | "done"
  | "cancelled";

export interface RoutingDecision {
  task_type: string;
  model_id: string;
  confidence: number;
  reason: string;
  fallback_model_id?: string;
}

export interface PlanStep {
  step_id: string;
  description: string;
  tool?: string;
  tool_args: Record<string, unknown>;
  status: "pending" | "running" | "done" | "failed" | "blocked";
}

export interface VerificationResult {
  passed: boolean;
  checks: Record<string, boolean>;
  notes: string[];
}

export interface Artifact {
  artifact_id: string;
  name: string;
  type: string;
  size_bytes: number;
  download_url: string;
}

export interface AgentJob {
  job_id: string;
  status: JobStatus;
  routing?: RoutingDecision;
  plan: PlanStep[];
  tool_calls: unknown[];
  observations: string[];
  verification?: VerificationResult;
  requires_human_approval: boolean;
  artifacts: Artifact[];
  final_answer?: string | null;
  error?: string | null;
}
```

---

# 27. API Client Layer

Create one Electron service:

```text
src/services/agentApi.ts
```

Example:

```ts
export async function createJob(
  request: CreateJobRequest
): Promise<CreateJobResponse>
```

```ts
export async function getJob(
  jobId: string
): Promise<AgentJob>
```

```ts
export async function approveJob(
  jobId: string,
  reviewerUserId: string
): Promise<AgentJob>
```

```ts
export async function cancelJob(
  jobId: string
): Promise<AgentJob>
```

```ts
export async function downloadArtifact(
  jobId: string,
  artifactId: string
): Promise<Blob>
```

All HTTP access belongs in this layer.

The UI should not call `fetch()` directly from arbitrary components.

---

# 28. Recommended Electron Components

```text
AgentWorkspace
├── TaskComposer
├── AttachmentTray
├── JobProgress
│   ├── RoutingCard
│   ├── PlanTimeline
│   ├── ToolTimeline
│   └── VerificationCard
├── ApprovalDialog
├── FinalAnswer
├── ArtifactList
└── AuditTimeline
```

---

# 29. Chat + Agent Activity UX

Recommended layout:

```text
+----------------------------------------------------+
| Task                                               |
| Read the P-101 report and draft approval note...   |
+----------------------------------------------------+

Model
Hermes Agent 8B
Reasoning + tool calling

PLAN
✓ Search inspection report
✓ Search vibration SOP
⟳ Generate approval note

TOOLS
✓ search_documents — 5 results
✓ search_documents — 3 results
⟳ generate_docx

VERIFICATION
Waiting...

ARTIFACTS
Nothing yet

FINAL ANSWER
...
```

The user sees meaningful activity without exposing private chain-of-thought.

---

# 30. Security UX

When something is blocked:

```text
Action blocked by security policy

Tool:
write_file

Reason:
Target location is outside the job workspace.
```

Do not show:

```text
Internal rule implementation details
```

that would make the system easier to attack.

---

# 31. Approval UX

A good approval card:

```text
┌─────────────────────────────────────┐
│ Human approval required             │
│                                     │
│ Action                              │
│ Generate approval note              │
│                                     │
│ Risk tier                           │
│ 2 — Review required                 │
│                                     │
│ Why                                 │
│ This action creates a formal        │
│ business artifact.                  │
│                                     │
│ [ Reject ]              [ Approve ] │
└─────────────────────────────────────┘
```

The reviewer should see:

```text
what action
why
which document(s)
what artifact will be created
```

without being shown hidden chain-of-thought.

---

# 32. Artifact UX

After completion:

```text
Generated artifacts

approval_note.docx
Word Document
48 KB

[Open] [Save As]
```

For multiple artifacts:

```text
pump_analysis.docx
pump_calculation.xlsx
test_results.txt
```

---

# 33. Failure UX

Do not show generic:

```text
Something went wrong.
```

Prefer:

```text
Agent failed

Stage:
Verification

Reason:
Required citation could not be validated.

The result was not delivered.
```

For backend failures:

```text
Model service unavailable

Please retry after the local model service is restored.
```

Never tell the user to connect to the Internet.

---

# 34. Offline Indicator

Since sovereignty is a key product feature, Electron can show:

```text
● ON-PREMISE
External network: BLOCKED
Model: LOCAL
Knowledge base: LOCAL
```

This should be backed by real backend/network telemetry.

Do not fabricate a green "offline" badge.

---

# 35. Network Proof Screen

Recommended optional screen:

```text
Sovereignty Monitor

External connections
0

Blocked egress attempts
0

Internal requests
127

Internet DNS requests
0
```

The data should come from the infrastructure monitoring service, not a hard-coded UI counter.

---

# 36. RAG Integration from Electron Perspective

Electron should not call RAG directly.

Correct:

```text
Electron
    ↓
Agent Orchestrator
    ↓
search_documents tool
    ↓
RAG service
```

Incorrect:

```text
Electron
    ↓
RAG directly
```

Why?

Because the agent backend must enforce:

```text
identity
ACL
tool policy
audit
citation tracking
```

---

# 37. Vision/OCR Integration

Same principle.

Electron submits:

```text
PDF/image
```

Agent decides:

```text
OCR
vision
RAG
combination
```

The frontend should not encode business logic such as:

```text
if PDF is scanned -> call OCR
```

That belongs in the orchestration layer.

---

# 38. Model Switching

Electron may display:

```text
Selected model:
Hermes Agent

Capability:
Tool Calling / Reasoning
```

But the backend should own model selection.

Optionally provide:

```text
Advanced:
Preferred model
```

Even then:

> A user's preference is a hint, not permission to bypass routing or security.

---

# 39. Retry Semantics

The client may safely retry:

```text
GET /agent/{job_id}
```

It should not blindly retry:

```text
POST /agent/{job_id}/approve
```

unless the API is explicitly idempotent.

For `POST /agent/run`, support an optional:

```text
client_request_id
```

to prevent duplicate jobs.

Example:

```json
{
  "client_request_id": "electron-session-abc-001"
}
```

The backend can return the existing job for the same request ID.

---

# 40. Authentication Boundary

For the MVP:

```text
Electron
 -> bearer token
 -> FastAPI
```

For production:

```text
Electron
 -> Keycloak / AD / SSO
 -> access token
 -> FastAPI
```

The backend should extract:

```text
user identity
groups
roles
department
clearance
```

from trusted authentication data.

Never accept a client-supplied "admin" flag.

---

# 41. Versioning

Use:

```text
/api/v1
```

When the contract changes incompatibly:

```text
/api/v2
```

Do not silently change:

```text
enum values
field meanings
artifact semantics
error codes
```

without versioning.

---

# 42. Contract Testing

The backend should publish an OpenAPI document.

FastAPI automatically provides:

```text
/openapi.json
/docs
```

Electron developers should generate or maintain TypeScript types from the OpenAPI contract.

This prevents:

```text
backend says:
requires_human_approval

frontend expects:
needsApproval
```

---

# 43. Recommended Development Workflow

Backend team:

```text
modify Pydantic schema
      ↓
run tests
      ↓
generate OpenAPI
      ↓
update frontend types
```

Frontend team:

```text
consume typed API
      ↓
render state
      ↓
never infer state from text
```

---

# 44. End-to-End Integration Test

The team should have one test that simulates:

```text
Electron request
      ↓
POST /run
      ↓
job created
      ↓
GET job
      ↓
status planning
      ↓
status acting
      ↓
tool events
      ↓
verification passed
      ↓
artifact created
      ↓
status done
      ↓
GET artifact
      ↓
download file
```

Second test:

```text
POST /run
      ↓
awaiting_approval
      ↓
POST /approve
      ↓
resume
      ↓
done
```

Third:

```text
POST /run
      ↓
awaiting_approval
      ↓
POST /approve approved=false
      ↓
failed
      ↓
no action executed after rejection
```

---

# 45. Integration Do Not's

Do not:

```text
call Ollama directly from Electron
call PostgreSQL from Electron
call RAG directly from Electron
execute Python in Electron
construct backend filesystem paths
parse model text for control flow
use chat text as approval
trust client-supplied authorization
```

---

# 46. Integration Must's

Always:

```text
call FastAPI
use versioned API
use structured status
use structured error codes
use artifact endpoints
use SSE/polling for progress
use explicit approval endpoint
use backend-provided URLs
```

---

# 47. Example Full Client Flow

User enters:

```text
Read the Pump P-101 inspection report
and create an approval note citing the SOP.
```

Electron:

```text
POST /files
```

receives:

```text
file-123
```

Then:

```text
POST /agent/run
```

receives:

```text
job-456
```

Electron opens:

```text
GET /agent/job-456/events
```

Events:

```text
model_selected
plan_created
step_started
tool_started
tool_completed
step_completed
verification_started
verification_passed
artifact_created
job_completed
```

UI shows:

```text
Completed

Approval note
approval_note.docx

Verification:
Passed

Sources:
3
```

The user clicks:

```text
Open
```

Electron calls:

```text
GET /agent/job-456/artifacts/art-789
```

and saves/opens the file.

---

# 48. Recommended Backend ↔ Electron Contract

The simplest mental model is:

```text
JOB
 |
 +-- status
 +-- routing
 +-- plan
 +-- activity
 +-- verification
 +-- approval
 +-- artifacts
 +-- final_answer
```

Electron renders this object.

FastAPI owns how the object is produced.

---

# 49. MVP API List

Implement exactly these first:

```text
POST   /api/v1/agent/run
GET    /api/v1/agent/{job_id}
POST   /api/v1/agent/{job_id}/approve
POST   /api/v1/agent/{job_id}/cancel
GET    /api/v1/agent/{job_id}/events
GET    /api/v1/agent/{job_id}/artifacts
GET    /api/v1/agent/{job_id}/artifacts/{artifact_id}
POST   /api/v1/files
GET    /health
GET    /ready
```

Keep the first version small.

---

# 50. Definition of Done for Electron Integration

Integration is complete when:

- Electron submits a task
- Electron uploads attachments
- Electron receives `job_id`
- Electron displays current status
- Electron displays model-routing information
- Electron displays plan
- Electron displays tool activity
- Electron displays verification
- Electron can handle approval
- Electron can cancel
- Electron receives completion event
- Electron displays final answer
- Electron downloads artifacts
- Electron handles backend errors by error code
- Electron works without knowing LangGraph internals
- Electron works without knowing which model provider is behind the API

---

# 51. Final Contract Principle

The clean architecture is:

```text
                 ELECTRON
                    |
                    | REST / SSE
                    v
             AGENT API CONTRACT
                    |
             +------+------+
             |             |
             v             v
        JOB SERVICE     EVENT SERVICE
             |
             v
        LANGGRAPH
             |
       +-----+------+
       |            |
       v            v
     MODELS       TOOLS
       |            |
       |      +-----+------+
       |      |            |
       |      v            v
       |     RAG         SANDBOX
       |
       v
     VERIFY
       |
       v
    APPROVAL
       |
       v
    ARTIFACT
       |
       v
      API
       |
       v
    ELECTRON
```

The frontend sees **jobs and events**.

The backend handles **reasoning, security, tools, verification, and execution**.

That boundary should remain stable even when the model, RAG implementation, OCR engine, sandbox technology, or database changes.
