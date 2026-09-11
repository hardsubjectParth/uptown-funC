# SIH 2026 — UPTOWN_FUNC

## Problem Statement 117

**Sovereign On-Premise Agentic AI Workbench using Open-Weight Multimodal LLMs for Confidential Industrial Work**

**Organization:** Mangalore Refinery and Petrochemicals Limited (MRPL)
**Theme:** Smart Automation
**Team:** UPTOWN_FUNC
**Event:** Smart India Hackathon 2026

---

## 1. Overview

UPTOWN_FUNC is developing a **sovereign, on-premise AI workbench** for confidential industrial environments.

The system is designed to enable organizations to use modern AI capabilities while keeping sensitive documents, enterprise data, processing workflows, and generated outputs within their own infrastructure.

The platform combines local language and multimodal models with document retrieval, controlled tool execution, workflow orchestration, and audit mechanisms.

The primary objective is to provide a practical alternative to cloud-dependent AI systems for environments where **data confidentiality, operational control, and traceability** are essential.

---

## 2. Problem

Industrial organizations work with large volumes of sensitive information, including:

* Engineering and technical documents
* Standard Operating Procedures (SOPs)
* Maintenance records
* Reports and spreadsheets
* Process documentation
* Internal databases
* Scanned documents and images
* Confidential business information

Conventional AI solutions often require data to be processed by external cloud services. For sensitive industrial workloads, this creates concerns related to:

* Data confidentiality
* Data sovereignty
* Regulatory compliance
* Vendor dependency
* Network availability
* Control over AI-generated actions
* Auditability

The challenge is therefore to provide AI-assisted productivity **without requiring confidential industrial information to leave the organization's controlled environment**.

---

## 3. Proposed Solution

The proposed solution is an **on-premise agentic AI workbench** that provides a controlled environment for interacting with local AI models, enterprise knowledge, and approved tools.

The system follows a local-first architecture:

```text
User
 │
 ▼
Application Interface
 │
 ▼
Task Orchestrator
 │
 ├───────────────┐
 │               │
 ▼               ▼
Model Router     Knowledge Retrieval
 │               │
 ▼               ▼
Local LLMs       Local Knowledge Base
 │               │
 └───────┬───────┘
         │
         ▼
   Tool Execution
         │
         ▼
    Verification
         │
         ▼
  Audit / Logging
         │
         ▼
      Output
```

The architecture is designed so that AI models, documents, tools, and generated artifacts can operate within the organization's infrastructure.

---

## 4. Key Capabilities

### Local AI Models

The platform supports locally hosted, open-weight models for:

* General reasoning
* Code generation
* Document understanding
* Multimodal processing
* Embeddings and retrieval

The model layer is abstracted from the orchestration layer so that models can be replaced or upgraded without redesigning the application.

---

### Document Processing

The system provides a local document ingestion and processing pipeline for sources such as:

* PDF
* DOCX
* TXT
* Markdown
* CSV
* XLSX / XLSM
* Images

The processing pipeline includes:

```text
Document
   ↓
Ingestion
   ↓
Text / OCR Extraction
   ↓
Normalization
   ↓
Chunking
   ↓
Indexing
   ↓
Retrieval
   ↓
Context for Model
```

This allows users to query and work with organizational knowledge without transferring documents to an external AI service.

---

### Retrieval-Augmented Generation

The knowledge layer combines document indexing and retrieval with local language models.

Typical workflow:

```text
User Query
    ↓
Query Processing
    ↓
Knowledge Retrieval
    ↓
Relevant Documents / Chunks
    ↓
Local Model
    ↓
Context-Aware Response
```

The approach is intended to reduce dependence on model-only knowledge and provide responses grounded in the organization's available documents.

---

### Agentic Task Execution

Instead of treating every request as a simple question-answer interaction, the system can decompose tasks into multiple operations.

A typical execution flow is:

```text
Request
  ↓
Classification
  ↓
Planning
  ↓
Tool / Model Selection
  ↓
Execution
  ↓
Observation
  ↓
Verification
  ↓
Result
```

Tasks can involve multiple tools and intermediate operations before producing the final result.

---

### Controlled Tool System

AI agents interact with explicitly registered tools rather than having unrestricted access to the host system.

Examples include:

| Capability          | Purpose                                      |
| ------------------- | -------------------------------------------- |
| Document Search     | Retrieve relevant organizational information |
| File Read           | Access permitted workspace files             |
| File Write          | Generate or modify permitted files           |
| Python Execution    | Perform controlled computation               |
| Document Generation | Generate DOCX reports                        |
| Spreadsheet         |                                              |
