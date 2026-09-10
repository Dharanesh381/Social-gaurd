# Social Guard: End-User & Evaluator Guide

**Project:** Social Guard: An Explainable AI Framework for Social Media Content Verification  
**Document:** USER_GUIDE.md  
**Version:** 1.0.0

---

## 1. Quick Start

### 1.1 Prerequisites
- Python 3.11+
- Google Chrome (or Chromium-based browser)
- PostgreSQL (Optional, runs with embedded SQLite by default)

### 1.2 Start Backend Server
```bash
# 1. Activate virtual environment
source .venv/bin/activate

# 2. Start FastAPI application on port 8000
PYTHONPATH=backend uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
Navigate to `http://127.0.0.1:8000/docs` to inspect interactive Swagger documentation.

---

## 2. Installing the Chrome Extension

1. Open Google Chrome and navigate to `chrome://extensions/`.
2. Enable **Developer mode** toggle in the top right corner.
3. Click **Load unpacked** in the top left.
4. Select the `extension/` directory from this repository:
   `/Users/dharanesh/Desktop/Social-gaurd/extension`
5. Pin the **Social Guard 🛡️** icon to your browser toolbar.

---

## 3. How to Use Social Guard

### Mode A: Instant Academic Demo Scenarios
1. Click the Social Guard extension icon in your browser toolbar.
2. Under **Test Scenarios**, click any of the preset buttons:
   - **`Likely Real`**: Loads a verified scientific announcement with high evidence ratings.
   - **`Uncertain`**: Loads an unverified local claim demonstrating neutral baseline fallback.
   - **`Likely Fake`**: Loads a debunked medical hoax demonstrating bot detection and fact-check contradiction.
3. Click **Analyze & Verify Content** to view real-time credibility scoring and XAI reasoning.

### Mode B: Verifying Live Web Pages
1. Navigate to any social media post or news article.
2. Highlight text on the page or open the Social Guard popup and click **Extract from Tab**.
3. Click **Analyze & Verify Content**.
4. The extension communicates with the local FastAPI backend to produce:
   - **Credibility Score (0–100)** and **5-tier Classification Band**
   - **AI Generation Probability (%)** (Orthogonal metric)
   - **Module Scores Breakdown** (Comments, Evidence, User Behaviour, Similarity)
   - **Why This Result?** (Ranked positive & negative factors)
   - **Evidence** (Third-party publisher ratings & source links)
   - **Similar Content** (Recycled narrative detection & timestamps)
