# 🌿 IP-SAKTI Sahayak (SIH-26045)
### *An Agentic, Multi-Domain RAG Assistant for Ayurvedic Intellectual Property & Regulatory Compliance*

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18.3.1-61DAFB.svg)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Vite-5.4-646CFF.svg)](https://vitejs.dev/)
[![TailwindCSS](https://img.shields.io/badge/TailwindCSS-3.4-38B2AC.svg)](https://tailwindcss.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2.60-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![Qdrant](https://img.shields.io/badge/Qdrant-Vector_DB-red.svg)](https://qdrant.tech/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 1. Project Information

- **Project Title:** IP-SAKTI Sahayak — AI Co-Pilot for Ayurvedic IP & Regulatory Compliance
- **PS ID:** SIH-26045
- **PS Title:** Developing an AI-driven Legal & Regulatory Advisory Assistant for Traditional Knowledge (AYUSH) & Intellectual Property
- **Category:** Software
- **Theme:** Smart Governance / Intellectual Property Rights (IPR) / AYUSH

---

## 2. Problem Statement

Navigating intellectual property and statutory compliance for **Ayurvedic, Siddha, and Unani (ASU)** formulations in India is exceptionally complex:
1. **Multi-Statute Fragmentation:** Innovators must concurrently navigate the *Patents Act 1970 (Sections 3(p), 3(d), 3(e))*, the *Biological Diversity Act 2002 / 2023 (NBA Form I/III)*, the *Drugs & Cosmetics Act 1940 (Rule 158B, Schedule T GMP)*, and *FSSAI Ayurveda Aahar Regulations 2022*.
2. **High Legal Screening Costs & Delays:** Patent attorney consultations cost ₹50,000–₹2,50,000 per formulation, with 3–4 weeks turnaround.
3. **High Rejection Rates & Biopiracy Risks:** Over 60% of herbal patent filings face objections due to unverified Traditional Knowledge (TKDL) prior art or non-compliance with Access & Benefit Sharing (ABS).
4. **General LLM Hallucinations:** Naive conversational models frequently fabricate section numbers, mix up food/drug regulations, and generate ungrounded legal advice.

---

## 3. Proposed Solution

**IP-SAKTI Sahayak** is an enterprise-grade agentic AI platform combining:
* **Deterministic Rules Engine:** Executes legally load-bearing classifications before vector retrieval—never relying on probabilistic guesswork.
* **Cyclic Multi-Agent LangGraph Machine:** Implements stateful orchestration, multi-domain dynamic fan-out (`Patent`, `ABS`, `Drug Regulation`), dynamic slot-filling clarification, and automated citation verification loops.
* **Hybrid Qdrant Retrieval:** Combines dense semantic vectors with lexical BM25 matching and server-side payload filtering to prevent regulatory cross-contamination.
* **Court-Grade Verification Guardrail:** Verifies every cited section against retrieved government gazette chunks; triggers retry loops or graceful grounded abstention if evidence is insufficient.

---

## 4. Key Features

- 💬 **Dynamic Chat Workspace:** Multi-turn legal Q&A with real-time streaming, clarification chips for ambiguous queries, and citation cards.
- 📜 **Live Statute Reader Drawer:** Slide-over drawer allowing side-by-side inspection of authentic bare-act provisions.
- ⚖️ **Formulation Audit Pre-Screening:** Qualitative banded risk assessment (*Likely Blocked*, *Borderline — Needs Evidence*, *Reasonably Viable*) evaluating Section 3(p), Section 3(e), and NBA Form III requirements.
- 🌿 **Decoupled Botanical Lexicon (`BOTANICAL_LEXICON`):** Normalized multi-lingual ingredient extraction (Hindi, Sanskrit, Regional names $\rightarrow$ Scientific binomials) independent of product category certainty.
- 🌐 **Dual-Jurisdiction Engine:** Air-gapped routing between Indian Domestic compliance and International Export standards (US FDA Botanical Guidance / EU EMA Directive 2004/24/EC).
- 🛡️ **Zero-Hallucination Guardrail:** Blocks unverified citations and degrades gracefully to explain missing statutory facts.

---

## 5. Technology Stack

| Component | Technology | Specification / Role |
|---|---|---|
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS | Reactive SPA with slide-over drawers and streaming chat interface |
| **Backend API** | FastAPI, Uvicorn, Pydantic v2 | High-performance asynchronous REST / ASGI service |
| **Agent Orchestrator** | LangGraph, LangChain Core | Cyclic state machine with dynamic routing and checkpointer memory |
| **Vector Engine** | Qdrant Cloud / Local Cluster | Hybrid Dense + Sparse BM25 vector search with payload filtering |
| **Embedding Models** | Google Gemini / `BAAI/bge-m3` | 1024-dim dense embeddings for multilingual legal texts |
| **Reranker Engine** | 6-Signal Legal Reranker + Neural Cross-Encoder | Statutory hierarchy weighting ($L_0-L_5$), citation boost, and MMR deduplication |
| **LLM Inference** | Google Gemini 2.5/3.6 Flash / Groq / LM Studio | Multi-tier LLM generation with fallback support |
| **Database / Memory** | MemorySaver / PostgreSQL | Session history and multi-turn state persistence |

---

## 6. Architecture

See [docs/architecture.md](docs/architecture.md) for the comprehensive architecture documentation.

```text
User ──► React 18 Frontend ──► FastAPI Gateway (/api/v1/chat)
                                       │
                                       ▼
                       LangGraph State Machine
           ┌───────────────────────────┼───────────────────────────┐
           ▼                           ▼                           ▼
    Understand Node              Classify Node               Clarify Node
    (Intent Routing)        (Deterministic Rules)       (Slot-Filling Gate)
           │                           │
           └───────────────────────────┴─► Decompose Node (Fan-Out)
                                               │
               ┌───────────────────────────────┼───────────────────────────────┐
               ▼                               ▼                               ▼
       Patent Retrieval                  ABS Retrieval               Regulation Retrieval
      (Patents Act 1970)             (Biological Diversity)          (D&C Act Rule 158B)
               │                               │                               │
               └───────────────────────────────┼───────────────────────────────┘
                                               ▼
                                  Qdrant Hybrid Vector Store
                                               │
                                               ▼
                                 6-Signal Reranker & Context Pruning
                                               │
                                               ▼
                                 Grounded LLM Answer Generator
                                               │
                                               ▼
                                  Citation Guardrail Node
                                 /                       \
                      [Passed]  ▼                         ▼ [Failed & Retry < 2]
                Verified Legal Advisory               Loop Back to Decompose
                + Exact Source Citations             (or Grounded Abstention)
```

---

## 7. Repository Structure

```text
PS_26045/
├── README.md                           # Main SIH project documentation
├── SUBMISSION_GUIDE.md                 # SIH 2026 repository submission checklist
├── CHANGELOG.md                        # Complete RAG architecture changelog
├── DOCKER.md                           # Docker containerization instructions
├── docker-compose.yml                  # Multi-container service orchestrator
├── LICENSE                             # MIT Open Source License
├── docs/
│   └── architecture.md                 # Detailed architectural specifications
├── submission/
│   ├── PRESENTATION.md                 # Presentation links and requirements
│   └── DEMO.md                         # Video demonstration links
├── assets/
│   └── screenshots/
│       └── README.md                   # UI walkthrough screenshots guide
└── code/
    ├── backend/                        # FastAPI + LangGraph core service
    │   ├── app/
    │   │   ├── api/routes/             # Chat, Audit, Health routes
    │   │   ├── core/                   # Rules engine, classifiers, decomposers
    │   │   ├── graph/                  # LangGraph nodes, edges, state
    │   │   ├── guardrails/             # Citation verification guardrail
    │   │   ├── llm/                    # Prompts & provider clients (Gemini/Groq)
    │   │   ├── retrieval/              # Hybrid Qdrant retriever & 6-signal reranker
    │   │   └── services/               # Chatbot & memory services
    │   ├── Dockerfile
    │   └── requirements.txt
    ├── frontend/                       # React 18 + Vite + Tailwind CSS app
    │   ├── src/
    │   │   ├── components/sahayak/     # Chat workspace, drawers, citations
    │   │   └── routes/                 # TanStack file-based routes
    │   ├── Dockerfile
    │   └── package.json
    └── ingestion/                      # Legal document chunking & vector indexing
        └── pipeline.py
```

---

## 8. Final Presentation

The presentation for SIH 2026 is linked in [submission/PRESENTATION.md](submission/PRESENTATION.md).

---

## 9. Demo Video

The prototype demonstration video link is available in [submission/DEMO.md](submission/DEMO.md).

---

## 10. Screenshots

Application screenshots and UI walkthroughs are detailed in [assets/screenshots/README.md](assets/screenshots/README.md).

---

## 11. Quick Start & Installation

### Option A — Run via Docker Compose (Fastest)

```bash
# 1. Clone repository
git clone https://github.com/punitr2007/PS_26045.git
cd PS_26045

# 2. Configure environment
cp code/backend/.env.example code/backend/.env
# Add your GEMINI_API_KEY, GROQ_API_KEY, and QDRANT credentials in code/backend/.env

# 3. Build and launch all services
docker compose up --build
```
* Frontend will be accessible at: `http://localhost:5173`
* Backend API docs at: `http://localhost:8001/docs`

---

### Option B — Run Locally (Development Mode)

#### 1. Start FastAPI Backend
```bash
cd code/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env with your API keys

uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

#### 2. Start React 18 Frontend
```bash
cd code/frontend
npm install
npm run dev
```
Open `http://localhost:5173` in your browser.

---

## 12. Impact & Expected Benefits

* ⚡ **99.8% Faster Legal Research:** Cuts regulatory pre-screening time from 3–4 weeks down to under 5 seconds.
* 💰 **90%+ Cost Reduction for MSMEs:** Democratizes legal screening for 10,000+ AYUSH startups without expensive upfront attorney fees.
* 🛡️ **Anti-Biopiracy & Heritage Protection:** Automated TKDL prior-art checks protect India's indigenous knowledge against ungrounded patent claims.
* 🌿 **Enforcing NBA ABS Compliance:** Automatically triggers mandatory Access & Benefit Sharing (Form I/III) requirements under the *Biological Diversity Amendment Act 2023*.

---

## 13. Future Scope

1. **Direct IPO / Patent Office API Integration:** Real-time synchronization with Indian Patent Advanced Search System (InPASS).
2. **Vernacular Multilingual Voice Interface:** Enabling grassroots Vaidyas and traditional healers to consult using Hindi, Tamil, Telugu, and Kannada voice queries.
3. **Automated Form 1 / Form III Filing Generator:** Generating pre-filled National Biodiversity Authority application drafts directly from formulation audits.