# Social Guard: An Explainable AI Framework for Social Media Content Verification

[![Build Status](https://img.shields.io/badge/build-passing-brightgreen.svg)]()
[![Tests](https://img.shields.io/badge/tests-87%20passed-success.svg)]()
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-0.141.1-009688.svg)]()
[![Manifest V3](https://img.shields.io/badge/Chrome%20Extension-Manifest%20V3-orange.svg)]()

> **College Mini-Project / Academic Research Framework**  
> An end-to-end multi-modal Explainable AI (XAI) system for verifying social media claims, detecting automated bot manipulation, identifying recycled viral hoaxes, and evaluating synthetic AI media.

---

## 🏛️ System Architecture

Social Guard fuses 5 specialized analytical modules and an independent AI generation detector into a single transparent credibility evaluation:

```
                      ┌────────────────────────┐
                      │ Social Media Post/DOM  │
                      └───────────┬────────────┘
                                  │
      ┌───────────────────────────┼───────────────────────────┐
      │                           │                           │
┌─────▼───────┐             ┌─────▼───────┐             ┌─────▼───────┐
│  Module 1   │             │  Module 2   │             │  Module 3   │
│  Comments   │             │  Evidence   │             │  Behaviour  │
│  (NLP+BERT) │             │ (FactCheck) │             │ (Isolation) │
└─────┬───────┘             └─────┬───────┘             └─────┬───────┘
      │                           │                           │
      └───────────────────────────┼───────────────────────────┘
                                  │
                                  │
      ┌───────────────────────────┼───────────────────────────┐
      │                           │                           │
┌─────▼───────┐             ┌─────▼───────┐             ┌─────▼───────┐
│  Module 4   │             │  Module 5   │             │ Decoupled   │
│ Similarities│             │Score Fusion │             │ AI Detector │
│(pHash+Decay)│             │   & XAI     │             │ (Gradients) │
└─────────────┘             └─────┬───────┘             └─────────────┘
                                  │
                                  ▼
                    ┌───────────────────────────┐
                    │  FinalAnalysisResult      │
                    │  - Credibility Score      │
                    │  - 5-Tier Classification  │
                    │  - Orthogonal AI Prob %   │
                    │  - Grounded XAI Reasons   │
                    └───────────────────────────┘
```

---

## 🚀 Key Modules & Analytical Foundations

1. **Module 1: Comment Analysis Engine**  
   Sentence-BERT semantic coordination, Shannon emoji entropy, and Z-score/IQR temporal comment burst detection.
2. **Module 2: Evidence-Based Verification Engine**  
   Automated claim extraction, Google Fact Check Tools API retrieval, continuous truth score normalization, and IFCN source credibility weighting.
3. **Module 3: User Behaviour Analysis Engine**  
   10-feature tabular profiling, median imputation, and unsupervised Isolation Forest anomaly detection.
4. **Module 4: Similar Content & Hashtag Analysis Engine**  
   Jaccard hashtag overlap, S-BERT semantic corpus search, perceptual image hashing (`pHash`), and temporal recycling decay.
5. **Module 5: Score Fusion & Explainability Engine**  
   Linear weighted combination ($0.20 \times C + 0.40 \times E + 0.15 \times B + 0.25 \times S$), 5-tier classification (`LIKELY REAL`, `PROBABLY REAL`, `UNCERTAIN`, `PROBABLY FAKE`, `LIKELY FAKE`), and grounded factor-ranked explainability synthesis.
6. **Decoupled AI-Generated Media Detector**  
   Orthogonal evaluation of spatial gradient variance and lexical uniformity.

---

## 📚 Complete Academic Documentation

- 📖 [ALGORITHMS.md](ALGORITHMS.md) — Comprehensive explanation of all algorithms, inputs, formulas, outputs, and limitations.
- 🏛️ [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) — Architectural overview, data flows, and tier interactions.
- 🔌 [API_DOCUMENTATION.md](API_DOCUMENTATION.md) — Full REST API contract and schema specification.
- 🗄️ [DATABASE_DESIGN.md](DATABASE_DESIGN.md) — Relational schema, indexes, and Mermaid ERD.
- 🧪 [TEST_REPORT.md](TEST_REPORT.md) — End-to-end scenario test matrix (116 automated tests passing).
- 📊 [EVALUATION_REPORT.md](EVALUATION_REPORT.md) — Accuracy, Precision, Recall, F1-score, and confusion matrix benchmarks.
- 🛡️ [SECURITY_PRIVACY.md](SECURITY_PRIVACY.md) — Security audit, privacy practices, and hardening checklist.
- 💻 [USER_GUIDE.md](USER_GUIDE.md) — Complete 21-part Operations & User Guide for Windows.

---

## ⚡ Quick Start (Windows PowerShell)

```powershell
# 1. Setup virtual environment and install dependencies
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt

# 2. Configure environment template
Copy-Item backend\.env.example backend\.env

# 3. Run complete test suite (116 tests)
$env:PYTHONPATH="backend"
.\venv\Scripts\python.exe -m pytest backend/tests -v

# 4. Start the FastAPI verification server
.\venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Loading the Chrome Extension:
1. Open Google Chrome $\to$ Navigate to `chrome://extensions/`.
2. Toggle **Developer mode** to ON.
3. Click **Load unpacked** $\to$ Select the `extension/` directory.
4. Open any post on X/Twitter, Reddit, or Instagram and click **Extract from Tab** $\to$ **Analyze & Verify Content**.

See [USER_GUIDE.md](USER_GUIDE.md) for full documentation on architecture, database persistence, evaluation, and troubleshooting.

---

## 📄 License & Academic Attribution
Developed as an academic research and engineering project demonstrating Explainable AI for social media content verification.
