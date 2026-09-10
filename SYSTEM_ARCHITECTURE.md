# Social Guard: System Architecture & Data Flow

**Project:** Social Guard: An Explainable AI Framework for Social Media Content Verification  
**Academic Document:** SYSTEM_ARCHITECTURE.md  
**Version:** 1.0.0 (Production Implemented)

---

## 1. High-Level Architecture

Social Guard follows a modular, micro-pipeline architecture consisting of four core tiers:
1. **Client / Extraction Tier:** Chrome Extension (Manifest V3) & Platform Extractors (Reddit DOM).
2. **API & Orchestration Tier:** FastAPI Asynchronous Service (`/analyze`, `/health`).
3. **Explainable AI Analytics Tier:** Analytical Modules 1–5 + Orthogonal AI Detector.
4. **Persistence & Knowledge Tier:** PostgreSQL / SQLite Async SQLAlchemy ORM & Historical Corpus.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        CHROME EXTENSION (MV3)                          │
│  [Popup UI] ── (REST JSON) ──> [Content Script: DOM Extractor]         │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP POST /analyze
┌───────────────────────────────────▼────────────────────────────────────┐
│                       FASTAPI BACKEND GATEWAY                          │
│  - Input Validation (Pydantic V2)                                      │
│  - CORS Middleware & Security Boundaries                               │
│  - Pipeline Orchestrator Service                                       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
    ┌───────────────────────────────┴───────────────────────────────┐
    │                                                               │
┌───▼──────────────────────────┐        ┌───────────────────────────▼───┐
│ ANALYTICAL AI MODULES (1–5)  │        │ DECOUPLED AI DETECTOR         │
│                              │        │                               │
│ 1. Comment Analysis Engine   │        │ - Image Gradient Variance     │
│ 2. Evidence Verification     │        │ - Text Lexical Uniformity     │
│ 3. User Behaviour Engine     │        │                               │
│ 4. Similar Content / Corpus  │        │ Returns orthogonal            │
│ 5. Linear Fusion & XAI Engine│        │ ai_generation_probability %   │
└───┬──────────────────────────┘        └───────────────────────────────┘
    │
┌───▼───────────────────────────────────────────────────────────────────┐
│               RELATIONAL PERSISTENCE & AUDIT TRAIL                    │
│  SQLAlchemy Async Session -> PostgreSQL / SQLite                      │
│  Tables: users, posts, comments, evidence, analysis_results           │
└───────────────────────────────────────────────────────────────────────┘
```

---

## 2. End-to-End Pipeline Data Flow

When a user triggers verification, the following execution sequence occurs:

```
Incoming AnalysisRequest
       │
       ▼
1. Validate Schema ────────────────> Reject Malformed (HTTP 422)
       │
       ▼
2. Comment Analysis (Module 1) ────> S-BERT Near-Duplicates + Emoji Entropy + Temporal Burst (0–100)
       │
       ▼
3. Evidence Verification (Module 2) > Google Fact Check API + Rating Normalizer (0–100)
       │
       ▼
4. User Behaviour (Module 3) ──────> Tabular Features + Isolation Forest Anomaly (0–100)
       │
       ▼
5. Similar Content (Module 4) ─────> Corpus Search + pHash Image + Temporal Recycling (0–100)
       │
       ▼
6. Score Fusion Engine (Module 5) ─> Linear Weighted Combination: 0.20*C + 0.40*E + 0.15*B + 0.25*S
       │
       ▼
7. Explainability Synthesis ───────> Rank Positive/Negative Factors + Summary String
       │
       ▼
8. Decoupled AI Media Detection ───> Standalone Synthetic Probability [0.0 - 100.0]
       │
       ▼
9. Asynchronous DB Persistence ────> Save Session Audit Record (users, posts, evidence, results)
       │
       ▼
Return FinalAnalysisResult (HTTP 200 OK)
```

---

## 3. Module Boundaries & Decoupling Guarantees

1. **Scraping vs. AI Isolation:**  
   Scraping and DOM parsing logic resides strictly in [`backend/app/platform/`](file:///Users/dharanesh/Desktop/Social-gaurd/backend/app/platform) and output standard domain objects (`SocialMediaPost`). AI modules never make platform-specific web requests.
2. **Orthogonal AI Generation Output:**  
   AI-generated media detection is an orthogonal metric. A synthetic image of a real event can convey truth; a human-shot photo can be repurposed for misinformation. The credibility score and AI probability remain strictly decoupled.
3. **Fault-Tolerant Persistence:**  
   Database write errors are caught and logged without failing the live verification response returned to the client.
