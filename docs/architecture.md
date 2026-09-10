# System Architecture — IP-SAKTI Sahayak (SIH-26045)

## 1. High-Level Flow

```text
                               ┌────────────────────────────────┐
                               │       User Web Interface       │
                               │      (React 18 + TanStack)     │
                               └───────────────┬────────────────┘
                                               │ HTTP / SSE (Port 5173 -> 8001)
                                               ▼
                               ┌────────────────────────────────┐
                               │        FastAPI Gateway         │
                               │       (/api/v1/chat API)       │
                               └───────────────┬────────────────┘
                                               │
                                               ▼
                               ┌────────────────────────────────┐
                               │   LangGraph State Orchestrator │
                               │     (Cyclic State Machine)     │
                               └───────┬───────────────▲────────┘
                                       │               │
        ┌──────────────────────────────┼───────────────┴──────────────────────────────┐
        │                              │                                              │
        ▼                              ▼                                              ▼
┌──────────────────┐         ┌──────────────────┐                           ┌──────────────────┐
│ Understand Node  │         │  Classify Node   │                           │   Clarify Node   │
│ (Intent Check)   │         │ (Deterministic   │                           │  (Slot-Filling   │
└───────┬──────────┘         │  Rules Engine)   │                           │   Clarification) │
        │                    └─────────┬────────┘                           └──────────────────┘
        ▼                              ▼
┌──────────────────┐         ┌─────────────────────────────────────────────────────────────────┐
│   Route Node     │         │                         Decompose Node                          │
│ (Jurisdiction)   │────────►│            (Multi-Domain Sub-Query Generator)                   │
└──────────────────┘         └─────────────────────────┬───────────────────────────────────────┘
                                                       │
                     ┌─────────────────────────────────┼─────────────────────────────────┐
                     │                                 │                                 │
                     ▼                                 ▼                                 ▼
         ┌───────────────────────┐         ┌───────────────────────┐         ┌───────────────────────┐
         │ Retrieve Patent Node  │         │   Retrieve ABS Node   │         │ Retrieve Regulation   │
         │ (Patents Act 1970 /   │         │ (Biological Diversity │         │ (D&C Act Rule 158B /  │
         │  Section 3p TKDL)     │         │  Act 2002 / 2023)     │         │  Schedule T GMP)      │
         └───────────┬───────────┘         └───────────┬───────────┘         └───────────┬───────────┘
                     │                                 │                                 │
                     └─────────────────────────────────┼─────────────────────────────────┘
                                                       │
                                                       ▼
                                     ┌──────────────────────────────────┐
                                     │     Qdrant Vector Database       │
                                     │  (Hybrid Dense + BM25 Sparse)    │
                                     └─────────────────┬────────────────┘
                                                       │
                                                       ▼
                                     ┌──────────────────────────────────┐
                                     │       Rerank & Generate          │
                                     │   (6-Signal + Neural Cross-Enc   │
                                     │   + MMR Deduplication)           │
                                     └─────────────────┬────────────────┘
                                                       │
                                                       ▼
                                     ┌──────────────────────────────────┐
                                     │      Guardrail Verification      │
                                     │   (Citation Match + Grounding)   │
                                     └─────────────────┬────────────────┘
                                                       │
                                      Pass ┌───────────┴───────────┐ Retry (<2)
                                           ▼                       ▼
                             ┌───────────────────────────┐   ┌───────────────────────────┐
                             │ Grounded Legal Advisory   │   │  Re-decompose & Loop Back │
                             │ + Section-Level Citations │   │  (or Grounded Abstention) │
                             └───────────────────────────┘   └───────────────────────────┘
```

## 2. Core Components

### A. Frontend Layer (React 18 + Vite + Tailwind CSS)
* **Chat Workspace:** Dynamic multi-turn chat stream with interactive clarification chips and grounded responses.
* **Live Statute Reader Drawer:** Slide-over drawer providing verified bare-act inspection for cited sections.
* **Formulation Audit Workspace:** Qualitative banded assessment (*Likely Blocked*, *Borderline*, *Reasonably Viable*) checking Section 3(p), 3(d), 3(e), and NBA Form I/III compliance.

### B. Backend API Gateway (FastAPI)
* Async high-throughput REST endpoints under `/api/v1/chat`, `/api/v1/audit`, and `/api/v1/health`.
* Built-in CORS handling supporting development, tunneling, and production domain origins.

### C. Agentic Workflow Engine (LangGraph)
* Stateful execution graph with in-memory `MemorySaver` or scalable PostgreSQL checkpointer.
* Non-linear execution paths allowing slot-filling clarification pauses and automatic retry loops upon guardrail failures.

### D. Multi-Domain Hybrid Retriever & Vector Database (Qdrant)
* **Dense + Sparse Hybrid Search:** High-dimensional semantic vectors paired with lexical BM25 matching for exact statute and section identification.
* **Server-Side Payload Filtering:** Strict pre-filtering across `act_name`, `legal_area`, and `jurisdiction` to prevent regulatory cross-contamination.

### E. 6-Signal Legal Reranker & Context Pruning
* Reranks candidate evidence based on statutory hierarchy ($L_0-L_5$), citation precision (+0.25 boost), text similarity, temporal recency, and MMR deduplication (`threshold=0.92`).

### F. Citation Verification Guardrail Node
* Validates every generated legal claim and citation against authentic retrieved statute chunks.
* Triggers automatic query re-decomposition or graceful grounded abstention if evidence is insufficient.
