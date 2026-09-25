# Social Guard — Comprehensive Evaluation Report

**Project:** Social Guard: An Explainable AI Framework for Social Media Content Verification  
**Evaluation Date:** September 24, 2026  
**Evaluation Dataset:** `datasets/processed/evaluation_dataset.json`  
**Evaluator Script:** `scripts/run_evaluation.py`  
**Benchmark Dataset Size:** N = 15 items  
**Label Distribution:** {'LIKELY REAL': 3, 'PROBABLY REAL': 3, 'UNCERTAIN': 3, 'PROBABLY FAKE': 3, 'LIKELY FAKE': 3}  

---

## 1. Executive Summary & Headline Metrics

The evaluation was executed on the standardized benchmark dataset covering 5 credibility tiers without altering the production scoring algorithms.

### 5-Tier Fine-Grained Classification Performance

| Metric | Score |
| :--- | :---: |
| **Overall Accuracy** | **40.00%** |
| **Macro Precision** | **30.00%** |
| **Macro Recall** | **40.00%** |
| **Macro F1-Score** | **33.33%** |

#### Per-Classification Breakdown (5-Tier)

| Classification | Support | Precision | Recall | F1-Score |
| :--- | :---: | :---: | :---: | :---: |
| **LIKELY REAL** | 3 | **100.0%** | **100.0%** | **100.0%** |
| **PROBABLY REAL** | 3 | **50.0%** | **100.0%** | **66.7%** |
| **UNCERTAIN** | 3 | **0.0%** | **0.0%** | **0.0%** |
| **PROBABLY FAKE** | 3 | **0.0%** | **0.0%** | **0.0%** |
| **LIKELY FAKE** | 3 | **0.0%** | **0.0%** | **0.0%** |

#### 5-Tier Confusion Matrix

```
Actual \ Pred      LIKELY REAL  PROBABLY REAL      UNCERTAIN  PROBABLY FAKE    LIKELY FAKE          Total
---------------------------------------------------------------------------------------------------------
LIKELY REAL                  3              0              0              0              0              3
PROBABLY REAL                0              3              0              0              0              3
UNCERTAIN                    0              3              0              0              0              3
PROBABLY FAKE                0              0              3              0              0              3
LIKELY FAKE                  0              0              2              1              0              3
```

---

### 3-Tier Consolidated Classification Performance

| Metric | Score |
| :--- | :---: |
| **Overall Accuracy** | **46.67%** |
| **Macro Precision** | **55.56%** |
| **Macro Recall** | **38.89%** |
| **Macro F1-Score** | **36.19%** |

#### Per-Tier Breakdown (3-Tier)

| Tier | Support | Precision | Recall | F1-Score |
| :--- | :---: | :---: | :---: | :---: |
| **REAL** | 6 | **66.7%** | **100.0%** | **80.0%** |
| **FAKE** | 6 | **100.0%** | **16.7%** | **28.6%** |
| **UNCERTAIN** | 3 | **0.0%** | **0.0%** | **0.0%** |

#### 3-Tier Confusion Matrix

```
Actual \ Pred       REAL       FAKE  UNCERTAIN      Total
---------------------------------------------------------
REAL                 6          0          0          6
FAKE                 0          1          5          6
UNCERTAIN            3          0          0          3
```

---

## 2. Module-Level Benchmarks

- **Evidence Verification Status Accuracy:** **100.0%**
- **User Behaviour Anomaly Detection Accuracy:** **80.0%**
- **Similar Content Match Accuracy:** **80.0%**

## 3. Latency & Performance Profile

- **Average End-to-End API Latency:** **1245.5 ms**
- **Module Timings Breakdown:**
  - `comment_analysis_ms`: 739.0 ms
  - `evidence_verification_ms`: 162.7 ms
  - `user_behaviour_ms`: 16.2 ms
  - `similar_content_ms`: 156.8 ms
  - `score_fusion_ms`: 0.0 ms
  - `ai_detection_ms`: 0.0 ms
  - `total_analysis_ms`: 0.0 ms

---

## 4. Dataset Specification & Synthetic Demarcation

The evaluation dataset (`datasets/processed/evaluation_dataset.json`) contains N = 15 representative items:
- **Synthetic / Demo Examples**: Marked with `"is_synthetic": true, "source_type": "synthetic"` to test known edge conditions (e.g. extreme follower asymmetry, recycled narratives, fabricated quotes).
- **Real-World Case Examples**: Marked with `"is_synthetic": false, "source_type": "real_world_case"` representing real social media occurrences (e.g., official NASA announcements, WHO advisories, debunked health rumors).

## 5. Limitations & Future Work

1. **Sample Size Scope**: N = 15 provides an essential calibration benchmark covering all 5 discrete decision bands, but larger automated corpora (e.g., 500+ items) will provide tighter confidence intervals.
2. **Real-Time Fact Check API Quotas**: Google Fact Check Tools API enforces rate limits on unpaid tiers; offline mock responses ensure deterministic automated regression testing.
3. **Absence of Evidence vs. Negative Evidence**: Unverified obscure statements default to 50/100 neutral baseline; benign local discussions without online fact-checks appropriately land in `PROBABLY REAL` or `UNCERTAIN` when organic user and comment signals are positive.
