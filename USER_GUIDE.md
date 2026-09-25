# Social Guard: Comprehensive User & Operations Guide

> **Final System Documentation (Phase 11)**  
> **Target Environment:** Windows 10/11 (PowerShell)  
> **Component Version:** 1.0.0 (FastAPI Backend + Chrome Extension Manifest V3)

---

## Table of Contents
1. [Project Purpose](#1-project-purpose)
2. [Architecture](#2-architecture)
3. [Technologies](#3-technologies)
4. [Installation](#4-installation)
5. [Windows Setup](#5-windows-setup)
6. [Virtual Environment](#6-virtual-environment)
7. [Environment Variables](#7-environment-variables)
8. [Google Fact Check API Setup](#8-google-fact-check-api-setup)
9. [SQLite Configuration](#9-sqlite-configuration)
10. [Starting FastAPI](#10-starting-fastapi)
11. [Loading Chrome Extension](#11-loading-chrome-extension)
12. [Using Social Guard](#12-using-social-guard)
13. [Supported Platforms](#13-supported-platforms)
14. [Post Extraction Limitations](#14-post-extraction-limitations)
15. [Comment Extraction Limitations](#15-comment-extraction-limitations)
16. [Analysis Pipeline](#16-analysis-pipeline)
17. [Credibility Classifications](#17-credibility-classifications)
18. [AI-Generation Detector](#18-ai-generation-detector)
19. [Database Persistence](#19-database-persistence)
20. [Evaluation Framework](#20-evaluation-framework)
21. [Troubleshooting Guide](#21-troubleshooting-guide)

---

## 1. Project Purpose

Social Guard is an end-to-end **Explainable Artificial Intelligence (XAI)** framework engineered to evaluate the credibility of social media content. Designed to combat disinformation, astroturfing campaigns, and generative AI deception, the system allows users to open any social media post in a Chromium browser, extract available post data with a single click, and receive transparent credibility scoring grounded in verifiable evidence and natural language explanations.

---

## 2. Architecture

Social Guard employs an asynchronous multi-tier architecture that isolates web extraction from analytical processing and database persistence:

```
┌─────────────────────────────────────────────────────────────┐
│                 Chrome Extension (Manifest V3)              │
│  - popup.html / popup.js (UI, Verdict Banner, XAI Reasons)  │
│  - content_extractor.js (DOM Extraction on X, Reddit, IG)   │
│  - api_client.js (Network Transport & Error Diagnostics)    │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP POST /analyze
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                  FastAPI Backend Gateway                    │
│  - Input Bounding & Pydantic Schema Validation (M1–M4)      │
│  - Least-Privilege CORS & Security Middleware               │
│  - Lifespan Pre-Warming (Sentence-BERT in Memory)           │
└──────────────────────────────┬──────────────────────────────┘
                               │ Orchestrates Execution
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 Pipeline Orchestrator Service               │
│  ├── M1: Comment Analysis Engine (S-BERT + Shannon Entropy) │
│  ├── M2: Evidence Verifier (Google Fact Check Tools API)    │
│  ├── M3: User Behaviour Analyzer (Isolation Forest Anomaly) │
│  ├── M4: Similar Content Engine (pHash + Temporal Decay)    │
│  ├── M5: Score Fusion Engine (0.20*M1+0.40*M2+0.15*M3+0.25) │
│  ├── Decoupled AI Detector (Laplacian Gradients + Lexical)  │
│  └── XAI Explainer (Factor-Ranked Support & Risk Rationale) │
└──────────────────────────────┬──────────────────────────────┘
                               │ Async Persistence
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                  SQLite Persistence Layer                   │
│  - Async SQLAlchemy + aiosqlite (social_guard.db)           │
│  - Normalized Tables: users, posts, comments, evidence, res │
│  - Automated Secret Scrubbing (_scrub_sensitive_data)       │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Technologies

| Layer | Technologies |
|---|---|
| **Backend Runtime** | Python 3.11+ (Validated on Python 3.14 on Windows) |
| **API Framework** | FastAPI 0.115+, Starlette, Uvicorn, Pydantic v2 |
| **NLP & Deep Learning** | Sentence-Transformers (`all-MiniLM-L6-v2`), PyTorch (CPU), Emoji |
| **Machine Learning** | Scikit-learn (Isolation Forest), NumPy, SciPy |
| **Computer Vision** | Pillow (PIL), ImageHash (Perceptual Hashing `pHash`), pytesseract (OCR) |
| **Networking & HTTP** | HTTPX (Async connection pooling with timeouts), BeautifulSoup4 |
| **Database** | SQLite 3 via SQLAlchemy 2.0 (Asyncio) and `aiosqlite` |
| **Browser Extension** | Chrome Extension Manifest V3, Vanilla JavaScript (ES6+), CSS3 Glassmorphism |
| **Testing & Evaluation**| Pytest, Pytest-Asyncio, Scikit-learn metrics |

---

## 4. Installation

Clone the repository and open Windows PowerShell in the root directory:

```powershell
git clone https://github.com/Dharanesh381/Social-gaurd.git
cd Social-gaurd
```

---

## 5. Windows Setup

Ensure that PowerShell script execution is enabled for the current process:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

Verify that Python is accessible on your system PATH:

```powershell
python --version
```

---

## 6. Virtual Environment

Create and activate a dedicated virtual environment:

```powershell
# Create virtual environment in '.venv' or 'venv'
python -m venv venv

# Activate the virtual environment in PowerShell
.\venv\Scripts\Activate.ps1

# Upgrade pip and install all backend requirements
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
```

---

## 7. Environment Variables

Create your local configuration by copying `backend/.env.example` to `backend/.env`:

```powershell
Copy-Item backend\.env.example backend\.env
```

Configuration parameters inside `backend/.env`:

| Variable | Default Value | Description |
|---|---|---|
| `APP_ENV` | `development` | Environment mode (`development` or `production`). |
| `DEBUG` | `True` | Enables detailed logging and interactive `/docs`. |
| `HOST` | `127.0.0.1` | Local bind address. |
| `PORT` | `8000` | Port for FastAPI server. |
| `SECRET_KEY` | *(Secret string)* | Session encryption key (validated in production). |
| `GOOGLE_FACT_CHECK_API_KEY` | *(Optional)* | Google Cloud API key for Fact Check Tools API. |
| `DATABASE_URL` | `sqlite+aiosqlite:///./social_guard.db` | Async database connection URL. |
| `SBERT_MODEL_NAME` | `all-MiniLM-L6-v2` | Sentence-BERT model name. |
| `WEIGHT_COMMENTS` | `0.20` | Module 1 fusion weight. |
| `WEIGHT_EVIDENCE` | `0.40` | Module 2 fusion weight. |
| `WEIGHT_USER_BEHAVIOUR` | `0.15` | Module 3 fusion weight. |
| `WEIGHT_SIMILAR_CONTENT` | `0.25` | Module 4 fusion weight. |

> [!IMPORTANT]
> `backend/.env` is ignored by Git and should never be committed to source control.

---

## 8. Google Fact Check API Setup

Social Guard uses the **Google Fact Check Tools API** for real-world claim verification:

1. Visit [Google Cloud Console Credentials](https://console.cloud.google.com/apis/credentials).
2. Create or select a project.
3. Enable the **Fact Check Tools API**.
4. Create an **API Key** and copy it.
5. In `backend/.env`, set:
   ```env
   GOOGLE_FACT_CHECK_API_KEY=AIzaSyYourActualKeyHere
   ```
6. **Graceful Fallback:** If the API key is omitted, Social Guard logs `GOOGLE_FACT_CHECK_API_KEY_NOT_CONFIGURED`, bypasses external network calls without failing, and applies a neutral **50.0/100** evidence baseline score.

---

## 9. SQLite Configuration

Social Guard uses an embedded async SQLite database (`social_guard.db`):

- **Automatic Initialization:** All relational tables (`users`, `posts`, `comments`, `evidence`, `analysis_results`) are generated automatically upon application startup.
- **Connection Flags:** Pre-configured with `check_same_thread: False` to support concurrent asynchronous operations.
- **Privacy Hardening:** Database files (`*.db`, `*.sqlite`) are untracked and ignored by Git to protect local user analysis history.

---

## 10. Starting FastAPI

Start the backend server using Windows PowerShell:

```powershell
# Set PYTHONPATH to include the backend directory
$env:PYTHONPATH="backend"

# Launch the Uvicorn server
.\venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Output confirming startup:
```
INFO:     Pre-warming Sentence-BERT model during application startup...
INFO:     Sentence-BERT model warmed up and ready in memory.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

Verify service status:
- **Health Check:** `http://127.0.0.1:8000/health`
- **Swagger Documentation:** `http://127.0.0.1:8000/docs` (available in development mode)

---

## 11. Loading Chrome Extension

1. Open Google Chrome (or Microsoft Edge / Brave).
2. Navigate to `chrome://extensions/`.
3. In the top-right corner, switch the **Developer mode** toggle to **ON**.
4. Click **Load unpacked** in the top-left corner.
5. In the file picker, select the `extension/` folder inside this repository.
6. Click the Extensions (puzzle piece) icon in your Chrome toolbar and pin **Social Guard 🛡️**.

---

## 12. Using Social Guard

### A. Real Post Mode (Live Browser Verification)
1. Open a social media post on **X/Twitter**, **Reddit**, or **Instagram**.
2. Click the **Social Guard** extension icon in your toolbar.
3. If not automatically populated, click **Extract from Tab**. The extension detects the author, text, hashtags, engagement counts, and comments from the active post.
4. Click **Analyze & Verify Content**.
5. Observe the 5-stage animated analysis loader:
   - *Extracting post...*
   - *Checking claims...*
   - *Analysing comments & user behaviour...*
   - *Checking similar content & image hashes...*
   - *Generating explainable credibility result...*
6. Review the structured results:
   - **Post Metadata Card:** Author handle, post snippet, comments count, likes.
   - **Main Credibility Verdict:** Final Score (0–100) and 5-tier classification badge.
   - **AI-Generation Detector:** Orthogonal probability percentage.
   - **Evidence & Fact-Checks:** Checked claims, publisher, rating category, and direct links.
   - **Analytical Module Meters:** Progress bars for Comments, Evidence, User Behaviour, and Similarity.
   - **Explainability ("Why This Result?"):** Grounded positive support factors and negative risk warnings.

### B. Demo Mode (Offline Academic Scenarios)
1. In the extension popup, click **Demo Mode**.
2. Choose one of the representative academic scenarios:
   - **`Likely Real`**: Peer-reviewed scientific discovery with credible evidence.
   - **`Uncertain`**: Early-stage unverified research demonstrating neutral baseline fallback.
   - **`Likely Fake`**: Medical bleach miracle hoax with bot spam comments and contradicted claims.
3. Click **Analyze & Verify Content** to test pipeline processing without active social media tabs.

---

## 13. Supported Platforms

| Platform | URL Patterns | Extracted Data Fields |
|---|---|---|
| **X / Twitter** | `x.com/*/status/*`, `twitter.com/*/status/*` | Text, Author handle, Timestamp, Likes, Reposts, Replies, Comments, Images |
| **Reddit** | `reddit.com/r/*/comments/*` | Post title & selftext, Author handle, Upvotes, Subreddit, Comments thread |
| **Instagram** | `instagram.com/p/*`, `instagram.com/reel/*` | Caption text, Author handle, Like counts, Comment list |
| **Generic** | Web articles / fallback input | Manual text input, pasted comments, custom weights |

---

## 14. Post Extraction Limitations

- **DOM Volatility:** Social networks periodically alter HTML class names and layout hierarchies. If an extraction fails, the user can manually paste the text into the popup editor.
- **Login Walls:** Instagram and X frequently restrict content inspection for unauthenticated or rate-limited guests.
- **Dynamic Thread Nesting:** Deeply nested sub-threads (replies of replies) may not be parsed if collapsed by default.

---

## 15. Comment Extraction Limitations

- **DOM Virtualization:** Modern single-page social media apps virtualize comment feeds, unmounting comments scrolled out of view. The content script extracts comments currently loaded in the active DOM viewport.
- **Platform Rate Limiting:** High-frequency extraction on consecutive posts may trigger temporary browser throttling by the target social network.

---

## 16. Analysis Pipeline

The verification engine processes each request through 9 deterministic stages:

```
Post Payload
   │
   ├── 1. Sanitization & Validation (Bounds on text, hashtags, media, comments)
   │
   ├── 2. Module 1: Comment Analysis Engine
   │      - S-BERT Semantic Coordination
   │      - Shannon Emoji Entropy
   │      - Temporal Burst Z-Score Detection
   │
   ├── 3. Module 2: Evidence Verification Engine
   │      - Rule-based Claim Extraction (filtering greetings/opinions)
   │      - Google Fact Check Tools API Query
   │      - Continuous Truth Normalization [0.0, 1.0]
   │      - IFCN Publisher Credibility Weighting
   │
   ├── 4. Module 3: User Behaviour Analysis Engine
   │      - 10 Tabular Behavioral Features
   │      - Median Imputation & Feature Scaling
   │      - Unsupervised Isolation Forest Anomaly Scoring
   │
   ├── 5. Module 4: Similar Content & Narrative Analysis
   │      - Jaccard Hashtag Coordination Overlap
   │      - S-BERT Semantic Vector Cosine Similarity
   │      - Perceptual Image Hashing (pHash with Hamming distance <= 6)
   │      - Exponential Temporal Decay for Recycled Viral Hoaxes
   │
   ├── 6. Module 5: Linear Score Fusion
   │      - Score = 0.20*M1 + 0.40*M2 + 0.15*M3 + 0.25*M4
   │      - Bounded Clamping [0.0, 100.0]
   │
   ├── 7. Decoupled Synthetic Media Detection
   │      - Spatial Laplacian Gradient Variance
   │      - Lexical Uniformity Metrics
   │
   ├── 8. Explainability Synthesis (XAI)
   │      - Factor Contribution Ranking (Top-3 Positive, Top-3 Negative)
   │      - Grounded Natural Language Summary
   │
   └── 9. Relational Database Persistence
          - Deduplication by request_id
          - Recursive Secret & Key Scrubbing
```

---

## 17. Credibility Classifications

The final credibility score is partitioned into 5 standardized credibility bands:

| Classification | Score Range | Meaning |
|---|---|---|
| **LIKELY REAL** | `80.0 – 100.0` | Strong verifiable evidence from accredited fact-checkers; organic user discussion. |
| **PROBABLY REAL** | `60.0 – 79.9` | Generally authentic indicators with minor unverified claims or low comment volume. |
| **UNCERTAIN** | `40.0 – 59.9` | Insufficient corroborating evidence or neutral baseline default; warrants scrutiny. |
| **PROBABLY FAKE** | `20.0 – 39.9` | Elevated risk markers: coordinated bot activity, high emoji entropy, or debunked claims. |
| **LIKELY FAKE** | `0.0 – 19.9` | Direct fact-check contradiction, viral recycled hoax match, or extreme bot patterns. |

---

## 18. AI-Generation Detector

The AI detector operates as an **orthogonal, decoupled metric**:

- **Decoupled Architecture:** A post discussing a real scientific event might use an AI-generated illustrative banner; conversely, an authentic human photograph can be repurposed with a fabricated caption. Therefore, the AI probability (`0.0% – 100.0%`) is displayed separately and does not distort the factual credibility score.
- **Evaluation Mechanism:** Utilizes spatial gradient variance across attached imagery and lexical perplexity distributions across text.

---

## 19. Database Persistence

All completed analyses are persisted in SQLite (`social_guard.db`) via SQLAlchemy:

- **Tables:**
  - `users`: Author usernames, account longevity, follower ratios, posting velocity.
  - `posts`: Platform, text, hashtags, media URLs, timestamps.
  - `comments`: Extracted text, commenter usernames, like counts, emojis.
  - `evidence`: Extracted claims, publisher name, source review URL, normalized truth score.
  - `analysis_results`: Request ID, final score, classification, AI probability, module scores, XAI explanations.
- **Deduplication:** Repeated analyses sharing identical request IDs are deduplicated.
- **Secret Scrubbing:** Raw API metadata and response payloads are recursively filtered to redact keys, tokens, and passwords.

---

## 20. Evaluation Framework

Social Guard includes an automated benchmark evaluation suite tested against representative multi-class scenarios in `datasets/processed/evaluation_dataset.json`:

```powershell
# Run the evaluation benchmark in PowerShell
$env:PYTHONPATH="backend"
.\venv\Scripts\python.exe scripts/run_evaluation.py
```

Benchmark output metrics:
- **Accuracy:** Overall multi-class prediction accuracy.
- **Precision, Recall, F1-Score:** Macro and weighted performance across all 5 credibility tiers.
- **Confusion Matrix:** True vs. predicted classification distribution.

---

## 21. Troubleshooting Guide

| Issue | Cause | PowerShell Resolution |
|---|---|---|
| **"Backend Offline (Port 8000)" in Extension** | FastAPI server is not running or blocked by firewall. | Run: `.\venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload` |
| **PowerShell: "cannot be loaded because running scripts is disabled"** | Windows execution policy blocks virtual environment activation. | Run: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned` |
| **First analysis takes several seconds** | Sentence-BERT downloading or loading weights into memory. | Normal on first boot. Startup lifespan now pre-warms S-BERT in RAM automatically. |
| **Evidence shows "API_KEY_MISSING"** | Google Fact Check API key not provided in `backend/.env`. | Expected behavior. Social Guard applies neutral 50.0 baseline score gracefully. |
| **"Failed to fetch" in extension** | Cross-Origin or host permission misconfiguration. | Verify `manifest.json` has `http://localhost:8000/*` and reload extension at `chrome://extensions/`. |
| **Database file locked error** | Simultaneous access on SQLite file. | System uses `check_same_thread: False` and connection pooling; restart FastAPI server if locked by another process. |

---

## 22. Running the Complete Automated Test Suite

To verify all 116 unit, integration, and security tests:

```powershell
# Run full pytest suite with verbose output
.\venv\Scripts\python.exe -m pytest backend/tests -v
```

All 116 tests should pass with 0 failures.
