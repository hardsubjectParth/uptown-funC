# UPTOWN_FUNC

## Smart India Hackathon 2026 — Problem Statement #117

### Sovereign On-Premise Agentic AI Workbench using Open-Weight Multimodal LLMs for Confidential Industrial Work

**Organization:** Mangalore Refinery and Petrochemicals Limited (MRPL)
**Theme:** Smart Automation
**Team:** UPTOWN_FUNC

---

## 1. Project Overview

Industrial organizations work with large volumes of confidential information such as technical documents, Standard Operating Procedures (SOPs), maintenance records, reports, spreadsheets, engineering data, and internal databases.

Using cloud-based AI services for such information can introduce concerns regarding **data confidentiality, data sovereignty, network dependency, vendor lock-in, and control over AI-driven operations**.

**UPTOWN_FUNC** addresses this problem by developing an **on-premise AI workbench** that enables organizations to use open-weight AI models, internal knowledge, and controlled automation tools while keeping sensitive workloads within their own infrastructure.

The platform brings together:

* Local Large Language Models (LLMs)
* Multimodal AI models
* Document processing
* Retrieval-Augmented Generation (RAG)
* Agent-based task orchestration
* Controlled tool execution
* Sandboxed computation
* Document and report generation
* Verification and audit logging

The objective is to provide a **controlled and extensible AI environment for confidential industrial work**.

---

# 2. Problem Statement

### The Challenge

Industrial organizations need AI assistance for tasks such as:

* Searching technical documentation
* Understanding large document repositories
* Analysing reports and spreadsheets
* Extracting information from scanned documents
* Generating reports and presentations
* Performing calculations and data analysis
* Automating repetitive knowledge-work tasks

However, sensitive industrial information cannot always be sent to external cloud AI services.

This creates several challenges:

| Challenge                | Concern                                                                |
| ------------------------ | ---------------------------------------------------------------------- |
| Confidential information | Sensitive data may leave the organization's infrastructure             |
| Cloud dependency         | AI functionality depends on external services and connectivity         |
| Data sovereignty         | Organizations have limited control over where information is processed |
| Vendor dependency        | Applications can become tightly coupled to a specific AI provider      |
| Autonomous actions       | Uncontrolled AI tool access can create security risks                  |
| Lack of traceability     | It can be difficult to determine how an AI result was produced         |

### Required Direction

The solution should allow AI to work with confidential organizational information while providing:

**Local processing + controlled access + useful automation + traceability**

---

# 3. Proposed Solution

UPTOWN_FUNC implements a **Sovereign AI Workbench** where the major components required for an AI-assisted workflow can operate inside the organization's infrastructure.

At a high level:

```text
                    ┌─────────────────────┐
                    │        USER         │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │    AI WORKBENCH     │
                    │                     │
                    │ Task Understanding  │
                    │ Planning             │
                    │ Orchestration        │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
       ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
       │ Local Models│  │ Local RAG   │  │ Tool System │
       │             │  │             │  │             │
       │ LLM         │  │ Documents   │  │ Files       │
       │ Vision      │  │ Retrieval   │  │ Python      │
       │ Embeddings  │  │ Knowledge   │  │ Reports     │
       └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
              │                │                │
              └────────────────┼────────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │    VERIFICATION     │
                    │                     │
                    │ Validation          │
                    │ Policy Checks       │
                    │ Approval            │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   AUDIT & OUTPUT    │
                    │                     │
                    │ Results             │
                    │ Reports             │
                    │ Generated Files     │
                    └─────────────────────┘
```

---

# 4. How the System Works

A typical user request passes through several stages.

### Step 1 — User Request

The user submits a task such as:

> "Analyse the maintenance reports for the last quarter and prepare a summary."

### Step 2 — Task Classification

The orchestrator determines what type of work is required.

For example:

```text
Document Analysis
        +
Knowledge Retrieval
        +
Data Processing
        +
Report Generation
```

### Step 3 — Planning

The system determines the operations required to complete the task.

```text
Understand request
       ↓
Find relevant documents
       ↓
Retrieve required information
       ↓
Analyse data
       ↓
Generate report
       ↓
Verify result
```

### Step 4 — Local Model / Tool Selection

The orchestrator selects appropriate local models and registered tools.

### Step 5 — Execution

The selected operations are executed within the controlled environment.

### Step 6 — Verification

Results are checked before being returned to the user.

### Step 7 — Output

The system produces the requested response or artifact, such as:

* Analysis
* Report
* Spreadsheet
* Presentation
* Structured data
* Processed document

---

# 5. Core Components

## 5.1 Agent Orchestrator

The orchestrator is responsible for managing the lifecycle of a task.

```text
Request
   ↓
Classification
   ↓
Planning
   ↓
Model / Tool Selection
   ↓
Execution
   ↓
Observation
   ↓
Verification
   ↓
Result
```

It provides the coordination layer between the user, AI models, knowledge sources, and tools.

---

## 5.2 Local Model Layer

The platform is designed around **open-weight models that can be hosted locally**.

Different models can be used for different workloads:

```text
General Reasoning
        │
        ▼
   General LLM

Coding Tasks
        │
        ▼
   Coding Model

Image / Document Understanding
        │
        ▼
   Vision Model

Knowledge Retrieval
        │
        ▼
   Embedding Model
```

The model interface is separated from the rest of the application, allowing models to be changed without changing the overall orchestration architecture.

---

# 6. Document Intelligence

Industrial information is distributed across multiple formats.

The system supports processing of:

* PDF
* DOCX
* TXT
* Markdown
* CSV
* XLSX
* XLSM
* Images

The document pipeline is:

```text
             Document
                 │
                 ▼
             Ingestion
                 │
                 ▼
        Text / Table / OCR
             Extraction
                 │
                 ▼
            Normalization
                 │
                 ▼
             Chunking
                 │
                 ▼
             Indexing
                 │
                 ▼
            Retrieval
```

This allows users to query organizational documents without requiring the documents themselves to be sent to an external AI service.

---

# 7. Retrieval-Augmented Generation

The RAG layer connects organizational knowledge with the local AI models.

Instead of relying only on the model's pretrained knowledge:

```text
User Query
    │
    ▼
Knowledge Retrieval
    │
    ▼
Relevant Documents
    │
    ▼
Relevant Content
    │
    ▼
Local LLM
    │
    ▼
Grounded Response
```

This approach allows responses to be based on the organization's own documents and information sources.

---

# 8. Multimodal Processing

Industrial information is not limited to plain text.

The platform is designed to work with:

* Text documents
* Scanned PDFs
* Images
* Tables
* Spreadsheets
* Mixed-format documents

OCR and multimodal models can be used when information cannot be obtained directly from document text.

This is particularly relevant for legacy documents and scanned industrial records.

---

# 9. Tool Execution

The agent does not receive unrestricted access to the operating system.

Instead, capabilities are exposed through a **controlled tool registry**.

Examples include:

| Tool             | Function                                          |
| ---------------- | ------------------------------------------------- |
| Document Search  | Search indexed organizational information         |
| File Read        | Read permitted files                              |
| File Write       | Create or modify permitted files                  |
| Python Execution | Perform controlled computation                    |
| OCR              | Extract information from images/scanned documents |
| Database Search  | Query approved data sources                       |
| DOCX Generation  | Generate Word reports                             |
| XLSX Generation  | Generate spreadsheets                             |
| PPTX Generation  | Generate presentations                            |
| Report Export    | Export structured results                         |

This provides a defined interface between AI-generated plans and actual system operations.

---

# 10. Sandboxed Execution

Some AI tasks require computation or code execution.

Allowing generated code to execute directly on the host system introduces unnecessary risk.

The platform therefore supports execution within an isolated environment with restrictions such as:

* Network restrictions
* Resource limits
* Controlled filesystem access
* Process isolation
* Execution time limits

The execution model is:

```text
AI Generated Code
        │
        ▼
Tool / Policy Check
        │
        ▼
Restricted Sandbox
        │
        ▼
Execution
        │
        ▼
Result
        │
        ▼
Verification
```

---

# 11. Security Model

Security is incorporated into the system architecture rather than being treated only as an external layer.

### Data Control

Sensitive information can remain within the organization's infrastructure.

### Tool Control

Agents can only use capabilities exposed through registered tools.

### Execution Isolation

Potentially unsafe operations can be performed in restricted environments.

### Policy Enforcement

Operations can be checked against configured policies.

### Human Approval

Selected operations can require explicit user authorization.

### Audit Logging

Important actions can be recorded for traceability.

---

# 12. Auditability

An enterprise AI system needs to provide visibility into how a result was produced.

The platform can maintain information about:

* Job execution
* Model selection
* Tool calls
* Retrieved sources
* Execution events
* Verification
* Generated artifacts
* Approvals

A simplified execution record can be represented as:

```text
User Request
     │
     ▼
   Job ID
     │
     ├── Model Selection
     │
     ├── Retrieved Sources
     │
     ├── Tool Calls
     │
     ├── Execution Results
     │
     ├── Verification
     │
     └── Final Artifact
```

This provides a foundation for monitoring, debugging, and governance.

---

# 13. Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                         USER                                │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    APPLICATION LAYER                        │
│                  Web UI / CLI / API                        │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   AGENT ORCHESTRATOR                       │
│                                                             │
│     Classification → Planning → Routing → Execution        │
└───────────────┬───────────────────────┬─────────────────────┘
                │                       │
                ▼                       ▼
┌─────────────────────────┐   ┌───────────────────────────────┐
│      MODEL LAYER        │   │         TOOL LAYER            │
│                         │   │                               │
│ Local LLMs              │   │ File Operations               │
│ Coding Models           │   │ Python Execution              │
│ Vision Models           │   │ Document Generation           │
│ Embedding Models        │   │ Database Access               │
└────────────┬────────────┘   └──────────────┬────────────────┘
             │                               │
             └───────────────┬───────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                     KNOWLEDGE LAYER                         │
│                                                             │
│  Ingestion → OCR → Processing → Indexing → Retrieval       │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  SECURITY & GOVERNANCE                       │
│                                                             │
│  Policies • Sandbox • Approvals • Verification • Audit     │
└─────────────────────────────────────────────────────────────┘
```

---

# 14. Technology Stack

| Layer         | Technologies                         |
| ------------- | ------------------------------------ |
| Language      | Python                               |
| AI Models     | Open-weight local LLMs               |
| Model Runtime | Ollama                               |
| Retrieval     | Local document indexing / embeddings |
| OCR           | Local OCR pipeline                   |
| Database      | SQLite / PostgreSQL                  |
| API           | REST / SSE                           |
| Frontend      | Web application                      |
| Containers    | Docker / Podman                      |
| Execution     | Isolated sandbox environments        |
| Testing       | Pytest                               |

The exact model and infrastructure configuration can be changed according to available hardware and deployment requirements.

---

# 15. Repository Structure

```text
SIH-2026-TEAM-UPTOWN_FUNC/
│
├── sovereign-agent-orchestrator/
│   │
│   ├── app/
│   │   ├── API and application components
│   │
│   ├── config/
│   │   └── Model and system configuration
│   │
│   ├── frontend/
│   │   └── User interface
│   │
│   ├── migrations/
│   │   └── Database migrations
│   │
│   ├── scripts/
│   │   └── Utility and deployment scripts
│   │
│   ├── tests/
│   │   └── Automated tests
│   │
│   ├── ARCHITECTURE.md
│   ├── SYSTEM_GUIDE.md
│   ├── TEAM_SETUP.md
│   ├── ELECTRON_INTEGRATION.md
│   ├── Dockerfile
│   ├── Containerfile
│   ├── docker-compose.yml
│   ├── cli.py
│   ├── pyproject.toml
│   └── requirements.txt
│
└── README.md
```

---

# 16. Installation

## Prerequisites

Depending on the selected deployment configuration:

* Python 3.x
* Git
* Ollama
* Docker or Podman
* Sufficient CPU / RAM / GPU resources for selected local models

---

## Clone the Repository

```bash
git clone https://github.com/hardsubjectParth/SIH-2026-TEAM-UPTOWN_FUNC.git

cd SIH-2026-TEAM-UPTOWN_FUNC
```

Enter the main application:

```bash
cd sovereign-agent-orchestrator
```

---

## Create a Virtual Environment

### Linux / macOS

```bash
python -m venv .venv
source .venv/bin/activate
```

### Windows

```powershell
python -m venv .venv
.venv\Scripts\activate
```

---

## Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Environment Configuration

Create the environment file:

### Linux / macOS

```bash
cp .env.example .env
```

### Windows

```powershell
copy .env.example .env
```

Configure the required application, model, database, and runtime settings in `.env`.

For the complete setup procedure, refer to:

* `SYSTEM_GUIDE.md`
* `TEAM_SETUP.md`
* `start.md`

---

# 17. Container Deployment

The project includes container deployment support.

### Docker

```bash
docker compose up --build
```

For Podman-based deployment, refer to the Podman documentation and configuration files included in the repository.

---

# 18. Testing

Run the automated test suite:

```bash
pytest
```

Additional tests and component-specific instructions are available in the `tests/` directory.

---

# 19. Example Workflow

A representative industrial workflow could look like:

### Request

```text
Analyse a set of maintenance reports and
generate a summary report containing
key findings and relevant observations.
```

### Processing

```text
Request
   ↓
Task Classification
   ↓
Document Search
   ↓
Relevant Report Retrieval
   ↓
Document / Table Processing
   ↓
Local Model Analysis
   ↓
Result Verification
   ↓
Report Generation
```

### Output

```text
Maintenance Analysis Report
├── Executive Summary
├── Relevant Findings
├── Supporting Information
├── Data Analysis
└── Generated Report
```

The same architecture can be adapted to other document-centric and knowledge-intensive industrial workflows.

---

# 20. Design Principles

### Sovereignty

Sensitive workloads should remain within the organization's controlled environment wherever possible.

### Least Privilege

AI agents should receive only the capabilities required for the task.

### Model Independence

The application should not be tightly coupled to one model provider.

### Controlled Autonomy

Agents should be capable of performing multi-step tasks without receiving unrestricted system access.

### Verification

Important results should pass through appropriate validation before delivery.

### Traceability

System actions should be observable and auditable.

### Extensibility

New models, tools, data sources, and workflows should be integrable without redesigning the entire system.

---

# 21. Intended Use Cases

The platform can support a range of confidential industrial knowledge-work scenarios, including:

* Technical document search
* SOP assistance
* Engineering document analysis
* Maintenance report analysis
* Internal knowledge retrieval
* Spreadsheet analysis
* Document summarization
* Automated report generation
* OCR-based document processing
* Controlled data analysis
* Enterprise knowledge assistance

The actual deployment and workflows should be configured according to the organization's security and operational requirements.
---

# 22. Future Scope

The platform can be extended with:

### Enterprise Integration

* Enterprise authentication
* Role-Based Access Control
* Internal databases
* Existing enterprise applications
* Additional document repositories

### Infrastructure

* GPU-based model serving
* Multi-node deployment
* High-availability configuration
* Air-gapped deployment

### Governance

* Advanced policy management
* Fine-grained permissions
* Enhanced audit and monitoring
* Approval workflows

### Industrial Applications

* Maintenance intelligence
* Engineering assistance
* SOP intelligence
* Technical knowledge management
* Operational report analysis

---

# 23. Project Information

|                       |                                                      |
| --------------------- | ---------------------------------------------------- |
| **Event**             | Smart India Hackathon 2026                           |
| **Problem Statement** | #117                                                 |
| **Organization**      | Mangalore Refinery and Petrochemicals Limited (MRPL) |
| **Theme**             | Smart Automation                                     |
| **Team**              | UPTOWN_FUNC                                          |
| **Project**           | Sovereign On-Premise Agentic AI Workbench            |

---

# 24. Team UPTOWN_FUNC

Developed for **Smart India Hackathon 2026** by Team **UPTOWN_FUNC**.

The project focuses on building practical, secure, and locally deployable AI infrastructure for confidential enterprise and industrial workloads.

---

## Disclaimer

This repository contains a prototype developed for Smart India Hackathon 2026.

The system should not be considered production-ready for industrial deployment without appropriate security assessment, performance testing, operational validation, access controls, compliance review, and organizational approval.

---

## License

Add the applicable license here if this project is intended for public distribution.

---

**UPTOWN_FUNC · Smart India Hackathon 2026 · Problem Statement #117**
