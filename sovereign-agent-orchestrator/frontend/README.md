# Sovereign AI Workbench --- Frontend

This document describes the frontend work currently implemented on the
`integration` branch so the backend team can understand the UI/API
integration and the contracts the frontend expects.

## Overview

The frontend is a React + TypeScript application built with Vite.

Current stack:

-   React 19
-   TypeScript
-   Vite
-   React Router
-   SWR
-   Geist font
-   FastAPI backend through REST APIs
-   Server-Sent Events (SSE) for agent job activity

The frontend does **not** access the database, models, RAG
implementation, or tools directly. It communicates with the FastAPI API
and renders the data returned by the backend.

------------------------------------------------------------------------

## Frontend structure

Important files/components:

``` text
frontend/
├── src/
│   ├── components/
│   │   ├── Artifacts.tsx
│   │   ├── KnowledgeBase.tsx
│   │   ├── Login.tsx
│   │   ├── MainContent.tsx
│   │   ├── NewTask.tsx
│   │   ├── ProtectedRoute.tsx
│   │   ├── RecentArtifacts.tsx
│   │   ├── RecentTasks.tsx
│   │   ├── Sidebar.tsx
│   │   └── Tasks.tsx
│   ├── context/
│   │   └── AuthContext.tsx
│   ├── services/
│   │   └── api.ts
│   ├── App.tsx
│   ├── main.tsx
│   └── index.css
└── package.json
```

`src/services/api.ts` is the main frontend-to-backend API boundary.

------------------------------------------------------------------------

# 1. Authentication

The frontend currently uses the backend's JWT authentication flow.

### Login

``` http
POST /api/v1/auth/dev/login
```

The frontend sends:

``` json
{
  "username": "...",
  "password": "..."
}
```

and expects:

``` json
{
  "access_token": "...",
  "token_type": "bearer",
  "expires_in": 900,
  "user": {
    "id": "...",
    "role": "admin | higher | lower",
    "tenant_id": "..."
  }
}
```

The JWT is then sent with authenticated requests:

``` http
Authorization: Bearer <token>
```

The frontend stores the authenticated user/token through `AuthContext`.

### Token expiry

The current development authentication token has a limited lifetime. If
an API request starts returning `401`, the user may need to log in
again.

------------------------------------------------------------------------

# 2. RBAC

The backend is the **source of truth for authorization**.

The frontend only uses the returned identity information to display the
user's role and adjust the UI.

Current roles:

-   `admin`
-   `higher`
-   `lower`

The frontend must **not** be considered a security boundary.

For example, hiding a button in React does not authorize or deny an
operation. The backend must continue validating the user's
role/permissions for every protected operation.

------------------------------------------------------------------------

# 3. Application routes

Current frontend routes:

  Route          Purpose
  -------------- ----------------------------------------
  `/login`       Authentication
  `/dashboard`   Main workbench dashboard
  `/new-task`    Create and monitor an agent task
  `/tasks`       Track an existing job by job ID
  `/knowledge`   Upload/search organizational knowledge
  `/artifacts`   View generated artifacts

Authenticated application pages are wrapped in `ProtectedRoute`.

The sidebar uses React Router `NavLink`, so the active page is
determined dynamically from the current URL.

------------------------------------------------------------------------

# 4. Backend health

The dashboard checks:

``` http
GET /api/v1/health
```

Expected response:

``` json
{
  "status": "ok"
}
```

The dashboard displays the backend/system status based on this response.

This is only a connectivity/status indicator; it does not replace the
backend's readiness or infrastructure monitoring.

------------------------------------------------------------------------

# 5. Knowledge Base

The Knowledge Base page now supports:

1.  Viewing authorized upload scopes
2.  Uploading documents
3.  Listing the user's accessible documents
4.  Searching organizational knowledge

## Upload scopes

The frontend requests:

``` http
GET /api/v1/files/scopes
```

Expected response:

``` json
{
  "scopes": [
    "..."
  ]
}
```

The backend determines which scopes the current user is allowed to use.

The frontend does not decide which security tier a user is authorized to
access.

## Upload

The frontend sends:

``` http
POST /api/v1/files
Content-Type: multipart/form-data
Authorization: Bearer <token>
```

Form fields:

``` text
file=<uploaded file>
scope=<selected scope>
```

The frontend expects a response containing at least:

``` json
{
  "file_id": "...",
  "name": "...",
  "mime_type": "...",
  "size_bytes": 12345,
  "index": {
    "tier": "..."
  }
}
```

The backend is responsible for:

-   validating authorization
-   validating upload limits
-   malware scanning
-   storing the file
-   indexing/ingesting the document
-   assigning the actual visibility/security tier
-   registering the file

The frontend simply displays the resulting metadata.

## List documents

The frontend calls:

``` http
GET /api/v1/files
```

Expected shape:

``` json
{
  "data": [
    {
      "id": "...",
      "name": "...",
      "metadata": {
        "visibility_tier": "...",
        "size_bytes": 12345,
        "mime_type": "application/pdf"
      },
      "created_at": "..."
    }
  ]
}
```

The Knowledge Base page displays:

-   document name
-   file type
-   file size
-   visibility tier

## Search

The frontend sends:

``` http
POST /api/v1/knowledge/search
```

with:

``` json
{
  "query": "...",
  "top_k": 8,
  "metadata": {}
}
```

The backend should continue enforcing tenant/role/document authorization
server-side.

The frontend expects search results containing:

``` json
{
  "data": [
    {
      "content": "...",
      "metadata": {},
      "score": 0.91
    }
  ]
}
```

------------------------------------------------------------------------

# 6. New Task

The New Task page is the main agent interaction UI.

The user can:

-   enter a natural-language task
-   attach files
-   select an available upload scope
-   submit the task
-   see the created job
-   watch agent activity
-   see the final answer

## Creating a job

The frontend calls:

``` http
POST /api/v1/agent/run
```

Request:

``` json
{
  "task": "Analyze the attached documents and summarize the findings.",
  "user_context": {},
  "attachments": [
    {
      "file_id": "..."
    }
  ]
}
```

The frontend expects:

``` json
{
  "job_id": "...",
  "status": "queued"
}
```

After receiving the `job_id`, the frontend starts monitoring that job.

The frontend does **not** directly call:

-   the model
-   the model router
-   RAG
-   tools
-   the database
-   the orchestrator

All of those remain backend responsibilities.

------------------------------------------------------------------------

# 7. Agent job status

The frontend can retrieve a job using:

``` http
GET /api/v1/agent/{job_id}
```

The job response contains information such as:

``` json
{
  "job_id": "...",
  "status": "planning",
  "task": "...",
  "routing": {},
  "plan": [],
  "tool_calls": [],
  "observations": [],
  "verification": {},
  "requires_human_approval": false,
  "artifacts": [],
  "final_answer": null,
  "error": null
}
```

The exact fields are defined by the backend contracts.

The Tasks page currently allows the user to enter a job ID and monitor
that job.

It polls the job endpoint periodically while the page is open.

------------------------------------------------------------------------

# 8. Agent activity / SSE

The New Task page also consumes the agent event stream:

``` http
GET /api/v1/agent/{job_id}/events
```

The frontend uses Server-Sent Events to display a human-readable
activity timeline.

Events currently recognized include:

``` text
job_created
status_changed
model_selected
model_response
plan_created
step_started
tool_started
tool_completed
observation
approval_required
verification_passed
verification_failed
artifact_created
job_completed
```

`status_changed` events are currently filtered from the visible activity
timeline because the job status is already displayed separately.

Example visible activity messages:

``` text
Task created
Selected model
Generated response
Created execution plan
Started execution step
Started tool
Completed tool
Received tool observation
Human approval required
Verification passed
Verification failed
Created artifact
Task completed
```

The SSE stream is already verified against the backend and the frontend
has successfully received real job events.

------------------------------------------------------------------------

# 9. Human approval

If the backend places a job into:

``` text
awaiting_approval
```

the frontend displays an approval-required notice.

The backend endpoint is:

``` http
POST /api/v1/agent/{job_id}/approve
```

with:

``` json
{
  "approved": true,
  "reviewer_user_id": "..."
}
```

The frontend currently exposes the job state/notice but approval UX is
not yet fully implemented.

The backend remains responsible for determining:

-   whether approval is required
-   who is authorized to approve
-   whether the approval is valid
-   resuming the job

------------------------------------------------------------------------

# 10. Artifacts

Jobs can contain generated artifacts.

The frontend expects artifact information from the backend, for example:

``` json
{
  "artifact_id": "...",
  "name": "report.docx",
  "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "size_bytes": 12345,
  "url": "..."
}
```

The backend exposes:

``` http
GET /api/v1/agent/{job_id}/artifacts
```

and:

``` http
GET /api/v1/agent/{job_id}/artifacts/{artifact_name}
```

The frontend should use the backend-provided artifact information rather
than constructing filesystem paths itself.

------------------------------------------------------------------------

# 11. API service layer

All frontend HTTP calls are centralized in:

``` text
src/services/api.ts
```

Current helpers include:

``` text
healthCheck()
devLogin()
getUploadScopes()
listFiles()
uploadFile()
searchKnowledge()
createAgentJob()
getJob()
jobEventsUrl()
streamJobEvents()
downloadArtifact()
```

This is intentional.

Components should not contain duplicated `fetch()` logic when the
request belongs in the API service layer.

If backend endpoints change, `api.ts` should normally be updated first,
followed by the component that consumes the changed response.

------------------------------------------------------------------------

# 12. Data flow

The intended architecture is:

``` text
┌──────────────────────────┐
│       React UI           │
│                          │
│ Dashboard                │
│ New Task                 │
│ Tasks                    │
│ Knowledge Base           │
│ Artifacts                │
└────────────┬─────────────┘
             │
             │ REST / SSE
             ▼
┌──────────────────────────┐
│       FastAPI API        │
│                          │
│ Auth / RBAC              │
│ Job API                  │
│ File API                 │
│ Knowledge API            │
│ Artifact API             │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│     Backend services     │
│                          │
│ Orchestrator             │
│ Model Router             │
│ RAG                      │
│ Tool Registry            │
│ Verification             │
│ Workspace                │
│ Storage / Database       │
└──────────────────────────┘
```

The React application should remain unaware of internal database
schemas, model implementations, RAG internals, and tool execution
details.

------------------------------------------------------------------------

# 13. Important backend integration expectations

### Backend owns authorization

Do not rely on frontend role checks for security.

Every sensitive endpoint should validate the authenticated identity and
permissions.

### Backend owns visibility tiers

The frontend displays the available upload scopes returned by:

``` http
GET /api/v1/files/scopes
```

It should not hard-code security tiers or assume that a user can upload
to a particular tier.

### Backend owns job lifecycle

The frontend renders job status and events.

The backend remains responsible for:

``` text
queued
planning
acting
observing
verifying
awaiting_approval
delivering
done
failed
cancelled
```

### Backend owns artifact storage

The frontend should consume artifact metadata and download endpoints
rather than accessing workspace paths.

### API response stability

The frontend is currently coupled to the response shapes described
above.

If backend response schemas change, please update the frontend API
service/types accordingly.

------------------------------------------------------------------------

# 14. Current limitations / not implemented yet

The following should **not** be assumed to be complete:

-   Full production authentication/OIDC integration
-   Complete approval UI
-   Full artifact management UX
-   A backend endpoint for listing all jobs/recent tasks
-   Real-time task list updates
-   Responsive/mobile polish
-   Monitoring/admin UI
-   Audit-log UI
-   User-management UI
-   Model-management UI
-   Electron packaging
-   Production deployment configuration

In particular, the dashboard should not fabricate "recent tasks" until
the backend exposes an appropriate jobs-list endpoint.

------------------------------------------------------------------------

# 15. Development notes

Frontend development:

``` powershell
cd frontend
npm install
npm run dev
```

Default Vite development server:

``` text
http://localhost:5173/
```

Backend development server:

``` text
http://127.0.0.1:8080
```

API base URL defaults to:

``` text
http://127.0.0.1:8080/api/v1
```

It can be overridden using:

``` text
VITE_API_BASE_URL
```

Example:

``` text
VITE_API_BASE_URL=http://127.0.0.1:8080/api/v1
```

------------------------------------------------------------------------

# 16. Recent frontend changes

The current frontend work includes:

-   React workbench routing and authenticated layout
-   JWT login integration
-   Protected routes
-   Dynamic sidebar navigation
-   Backend health indicator
-   Knowledge Base document upload
-   Knowledge Base document listing
-   Knowledge Base search
-   Upload-scope retrieval from backend
-   New Task chat-style interface
-   File attachments for agent jobs
-   Agent job creation
-   Job polling
-   SSE agent activity timeline
-   Human-readable agent event messages
-   Tasks/job tracking page
-   Artifact integration foundation
-   Geist font integration
-   Shared API service layer
-   Updated workbench styling

------------------------------------------------------------------------

## Backend team quick reference

If you are changing the backend, these are the main frontend
dependencies:

``` text
GET  /api/v1/health
POST /api/v1/auth/dev/login

GET  /api/v1/files/scopes
GET  /api/v1/files
POST /api/v1/files

POST /api/v1/knowledge/search

POST /api/v1/agent/run
GET  /api/v1/agent/{job_id}
GET  /api/v1/agent/{job_id}/events
POST /api/v1/agent/{job_id}/approve
POST /api/v1/agent/{job_id}/cancel

GET  /api/v1/agent/{job_id}/artifacts
GET  /api/v1/agent/{job_id}/artifacts/{artifact_name}
```

## Development Authentication

The backend currently provides development login accounts for local testing.

| Username | Role |
|---|---|
| `admin` | Admin |
| `higher` | Higher |
| `lower` | Lower |

Login through:

`POST /api/v1/auth/dev/login`

The development passwords are configured through the local `.env` file:

```env
DEV_ADMIN_PASSWORD=...
DEV_HIGHER_PASSWORD=...
DEV_LOWER_PASSWORD=...

The key principle is:

> **Frontend = presentation + user interaction. Backend =
> authorization + orchestration + data + security + execution.**

This separation should allow the backend and frontend to evolve
independently as long as the API contracts remain stable.
