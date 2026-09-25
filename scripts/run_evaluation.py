"""
Evaluation Framework Runner for Social Guard.

Executes the standardized evaluation benchmark dataset through:
1. End-to-End Credibility Verification Pipeline
2. Individual Analytical Module Benchmarks (Evidence, User Behaviour, Similar Content)
3. Performance Benchmarks (API latency, module timings, total execution time)
4. Metrics calculation: Accuracy, Precision, Recall, F1-Score, Confusion Matrix (5-tier & 3-tier)
5. Generates structured evaluation summaries and updates EVALUATION_REPORT.md.
"""

import json
import os
import sys
import time
from typing import Any, Dict, List
from unittest.mock import AsyncMock

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from fastapi.testclient import TestClient
from app.main import app
from app.modules.evidence_verification.factcheck_client import fact_check_client
from app.modules.evidence_verification.analyzer import evidence_verifier


def load_dataset(dataset_path: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Load benchmark dataset and metadata."""
    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data, data.get("items", [])


def map_classification_to_ground_truth(classification: str) -> str:
    """Map 5-tier classification band to 3-class ground truth (REAL, FAKE, UNCERTAIN)."""
    if classification in ["LIKELY REAL", "PROBABLY REAL"]:
        return "REAL"
    elif classification in ["LIKELY FAKE", "PROBABLY FAKE"]:
        return "FAKE"
    else:
        return "UNCERTAIN"


def calculate_classification_metrics(y_true: List[str], y_pred: List[str], classes: List[str]) -> dict[str, Any]:
    """Calculate Multi-class Accuracy, Per-Class Precision/Recall/F1, and Confusion Matrix."""
    total = len(y_true)
    if total == 0:
        return {}

    correct = sum(1 for yt, yp in zip(y_true, y_pred) if yt == yp)
    accuracy = correct / total

    # Confusion matrix: rows = true, cols = pred
    matrix = {c_true: {c_pred: 0 for c_pred in classes} for c_true in classes}
    for yt, yp in zip(y_true, y_pred):
        if yt in matrix and yp in matrix[yt]:
            matrix[yt][yp] += 1

    per_class = {}
    for c in classes:
        tp = matrix[c][c]
        fp = sum(matrix[other][c] for other in classes if other != c)
        fn = sum(matrix[c][other] for other in classes if other != c)

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

        per_class[c] = {
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1_score": round(f1, 4),
            "support": sum(matrix[c].values()),
        }

    valid_classes = [c for c in classes if per_class[c]["support"] > 0]
    div_count = len(valid_classes) if valid_classes else len(classes)
    macro_prec = sum(per_class[c]["precision"] for c in valid_classes) / div_count
    macro_rec = sum(per_class[c]["recall"] for c in valid_classes) / div_count
    macro_f1 = sum(per_class[c]["f1_score"] for c in valid_classes) / div_count

    return {
        "accuracy": round(accuracy, 4),
        "macro_precision": round(macro_prec, 4),
        "macro_recall": round(macro_rec, 4),
        "macro_f1": round(macro_f1, 4),
        "per_class": per_class,
        "confusion_matrix": matrix,
    }


def format_confusion_matrix(matrix: dict[str, dict[str, int]], classes: list[str]) -> str:
    """Format confusion matrix as a clear text table."""
    col_width = max(max(len(c) for c in classes), 8) + 2
    header = f"{'Actual \\ Pred':<{col_width}}" + "".join(f"{c:>{col_width}}" for c in classes) + f"{'Total':>{col_width}}"
    separator = "-" * len(header)
    rows = [header, separator]

    for c_true in classes:
        row_total = sum(matrix[c_true].values())
        row_vals = "".join(f"{matrix[c_true][c_pred]:>{col_width}}" for c_pred in classes)
        rows.append(f"{c_true:<{col_width}}{row_vals}{row_total:>{col_width}}")

    return "\n".join(rows)


def run_evaluation() -> dict[str, Any]:
    """Execute end-to-end evaluation benchmark."""
    client = TestClient(app)
    dataset_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "datasets", "processed", "evaluation_dataset.json"))
    meta, items = load_dataset(dataset_path)
    print(f"\n=======================================================================")
    print(f" SOCIAL GUARD EVALUATION BENCHMARK RUNNER")
    print(f" Loaded {len(items)} benchmark test items from: {dataset_path}")
    print(f"=======================================================================")

    classes_5 = ["LIKELY REAL", "PROBABLY REAL", "UNCERTAIN", "PROBABLY FAKE", "LIKELY FAKE"]
    classes_3 = ["REAL", "FAKE", "UNCERTAIN"]

    y_true_5 = []
    y_pred_5 = []
    y_true_3 = []
    y_pred_3 = []

    # Label distribution tracker
    label_distribution = {}
    for it in items:
        lbl = it.get("expected_classification", "UNCERTAIN")
        label_distribution[lbl] = label_distribution.get(lbl, 0) + 1

    # Latency tracking
    api_latencies = []
    module_timings = {
        "comment_analysis_ms": [],
        "evidence_verification_ms": [],
        "user_behaviour_ms": [],
        "similar_content_ms": [],
        "score_fusion_ms": [],
        "ai_detection_ms": [],
        "total_analysis_ms": [],
    }

    # Module specific tracking
    evidence_results = []
    user_behaviour_results = []
    similar_content_results = []
    item_run_records = []

    for idx, item in enumerate(items, 1):
        expected_5 = item.get("expected_classification")
        expected_3 = item.get("ground_truth")
        y_true_5.append(expected_5)
        y_true_3.append(expected_3)

        # Mock fact check API response if provided in item for deterministic benchmarking
        mock_fc = item.get("mock_fact_check_response")
        if mock_fc is not None:
            fact_check_client.search_claims = AsyncMock(return_value=mock_fc)
            evidence_verifier.api_client.search_claims = AsyncMock(return_value=mock_fc)

        post_payload = {
            "request_id": f"eval_run_{item['id']}",
            "post": item["post"]
        }

        t0 = time.perf_counter()
        resp = client.post("/analyze", json=post_payload)
        t1 = time.perf_counter()
        latency_ms = (t1 - t0) * 1000.0
        api_latencies.append(latency_ms)

        if resp.status_code == 200:
            data = resp.json()
            raw_class = data.get("classification", "UNCERTAIN")
            predicted_3 = map_classification_to_ground_truth(raw_class)

            y_pred_5.append(raw_class)
            y_pred_3.append(predicted_3)

            timings = data.get("module_results", {}).get("timings_ms", {})
            for k in module_timings.keys():
                if k in timings:
                    module_timings[k].append(timings[k])

            breakdowns = data.get("module_results", {}).get("module_breakdowns", {})
            all_flags = data.get("module_results", {}).get("flags", [])
            fused_score = data.get("consolidated_score", 0.0)

            # Record module evaluation stats
            ev_data = breakdowns.get("evidence", {})
            ev_status = ev_data.get("status")
            evidence_match = (item.get("expected_evidence_status") == ev_status)
            evidence_results.append({
                "id": item["id"],
                "expected": item.get("expected_evidence_status"),
                "actual": ev_status,
                "match": evidence_match,
            })

            ub_data = breakdowns.get("user_behaviour", {})
            is_anom = ("NEW_ACCOUNT_HIGH_POSTING_VELOCITY" in all_flags or
                       "ANOMALOUS_BEHAVIOURAL_PATTERN" in all_flags or
                       ub_data.get("anomaly_score", 0.0) > 0.50)
            user_behaviour_match = (item.get("expected_user_anomaly") == is_anom)
            user_behaviour_results.append({
                "id": item["id"],
                "expected_anomaly": item.get("expected_user_anomaly"),
                "actual_anomaly": is_anom,
                "match": user_behaviour_match,
                "flags": all_flags,
            })

            sim_data = breakdowns.get("similarity", {})
            recycled = (sim_data.get("recycled_content", False) or
                        "RECYCLED_HISTORICAL_CONTENT_DETECTED" in all_flags or
                        "MATCHES_KNOWN_DEBUNKED_VIRAL_NARRATIVE" in all_flags)
            sim_match = (item.get("expected_recycled_content") == recycled)
            similar_content_results.append({
                "id": item["id"],
                "expected_recycled": item.get("expected_recycled_content"),
                "actual_recycled": recycled,
                "match": sim_match,
            })

            is_correct_5 = (raw_class == expected_5)
            is_correct_3 = (predicted_3 == expected_3)
            status_icon = "[OK]" if is_correct_5 else "[DIFF]"

            item_run_records.append({
                "id": item["id"],
                "name": item["name"],
                "expected_5": expected_5,
                "predicted_5": raw_class,
                "expected_3": expected_3,
                "predicted_3": predicted_3,
                "score": fused_score,
                "correct_5": is_correct_5,
                "correct_3": is_correct_3,
                "latency_ms": round(latency_ms, 2)
            })

            print(f" [{idx:02d}/{len(items):02d}] {status_icon} Item {item['id']}: Score={fused_score:5.1f} | Pred='{raw_class}' | Expected='{expected_5}' | Latency={latency_ms:6.1f}ms")
        else:
            y_pred_5.append("UNCERTAIN")
            y_pred_3.append("UNCERTAIN")
            print(f" [{idx:02d}/{len(items):02d}] [FAIL] Item {item['id']} HTTP Error {resp.status_code}")

    # 1. 5-Tier Metrics
    metrics_5 = calculate_classification_metrics(y_true_5, y_pred_5, classes_5)
    # 2. 3-Tier Metrics
    metrics_3 = calculate_classification_metrics(y_true_3, y_pred_3, classes_3)

    # Averages
    avg_api_latency = sum(api_latencies) / len(api_latencies) if api_latencies else 0.0
    avg_timings = {k: round(sum(v) / len(v), 2) if v else 0.0 for k, v in module_timings.items()}

    # Module accuracy stats
    ev_acc = sum(1 for e in evidence_results if e["match"]) / len(evidence_results) if evidence_results else 0.0
    ub_acc = sum(1 for u in user_behaviour_results if u["match"]) / len(user_behaviour_results) if user_behaviour_results else 0.0
    sim_acc = sum(1 for s in similar_content_results if s["match"]) / len(similar_content_results) if similar_content_results else 0.0

    # Print Formatted Results
    print("\n" + "=" * 70)
    print(" 5-TIER CREDIBILITY CLASSIFICATION RESULTS")
    print("=" * 70)
    print(f" Total Dataset Size:       {len(items)}")
    print(f" Label Distribution:       {label_distribution}")
    print(f" Overall Accuracy:         {metrics_5['accuracy'] * 100:.2f}%")
    print(f" Macro Precision:          {metrics_5['macro_precision'] * 100:.2f}%")
    print(f" Macro Recall:             {metrics_5['macro_recall'] * 100:.2f}%")
    print(f" Macro F1-Score:           {metrics_5['macro_f1'] * 100:.2f}%\n")

    print(" Per-Classification Performance Breakdown:")
    print(f" {'Classification':<16} {'Support':>8} {'Precision':>12} {'Recall':>10} {'F1-Score':>10}")
    print(" " + "-" * 58)
    for c in classes_5:
        p_c = metrics_5["per_class"][c]
        print(f" {c:<16} {p_c['support']:>8} {p_c['precision']*100:>11.1f}% {p_c['recall']*100:>9.1f}% {p_c['f1_score']*100:>9.1f}%")

    print("\n 5-Tier Confusion Matrix:")
    print(format_confusion_matrix(metrics_5["confusion_matrix"], classes_5))

    print("\n" + "=" * 70)
    print(" 3-TIER CONSOLIDATED CLASSIFICATION RESULTS")
    print("=" * 70)
    print(f" Overall Accuracy:         {metrics_3['accuracy'] * 100:.2f}%")
    print(f" Macro Precision:          {metrics_3['macro_precision'] * 100:.2f}%")
    print(f" Macro Recall:             {metrics_3['macro_recall'] * 100:.2f}%")
    print(f" Macro F1-Score:           {metrics_3['macro_f1'] * 100:.2f}%\n")

    print(" Per-Tier Performance Breakdown:")
    print(f" {'Tier':<12} {'Support':>8} {'Precision':>12} {'Recall':>10} {'F1-Score':>10}")
    print(" " + "-" * 54)
    for c in classes_3:
        p_c = metrics_3["per_class"][c]
        print(f" {c:<12} {p_c['support']:>8} {p_c['precision']*100:>11.1f}% {p_c['recall']*100:>9.1f}% {p_c['f1_score']*100:>9.1f}%")

    print("\n 3-Tier Confusion Matrix:")
    print(format_confusion_matrix(metrics_3["confusion_matrix"], classes_3))

    print("\n" + "=" * 70)
    print(" MODULE-LEVEL ACCURACY & LATENCY BENCHMARKS")
    print("=" * 70)
    print(f" Evidence Status Match Rate:       {ev_acc * 100:.1f}%")
    print(f" User Anomaly Detection Match Rate:{ub_acc * 100:.1f}%")
    print(f" Similar Content Match Rate:       {sim_acc * 100:.1f}%")
    print(f" Average API Request Latency:      {avg_api_latency:.1f} ms")
    print(f" Average Module Timings:           {avg_timings}")

    evaluation_summary = {
        "dataset_size": len(items),
        "label_distribution": label_distribution,
        "metrics_5_tier": metrics_5,
        "metrics_3_tier": metrics_3,
        "module_benchmarks": {
            "evidence_status_accuracy": round(ev_acc, 4),
            "user_anomaly_accuracy": round(ub_acc, 4),
            "similar_content_accuracy": round(sim_acc, 4),
        },
        "latencies": {
            "avg_api_latency_ms": round(avg_api_latency, 2),
            "avg_module_timings_ms": avg_timings,
        },
        "item_results": item_run_records,
    }

    # Save report update
    export_markdown_report(evaluation_summary, classes_5, classes_3)

    return evaluation_summary


def export_markdown_report(summary: dict[str, Any], classes_5: list[str], classes_3: list[str]):
    """Export formatted results into EVALUATION_REPORT.md."""
    report_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "EVALUATION_REPORT.md"))
    m5 = summary["metrics_5_tier"]
    m3 = summary["metrics_3_tier"]
    dist = summary["label_distribution"]

    lines = [
        "# Social Guard — Comprehensive Evaluation Report",
        "",
        "**Project:** Social Guard: An Explainable AI Framework for Social Media Content Verification  ",
        f"**Evaluation Date:** September 24, 2026  ",
        "**Evaluation Dataset:** `datasets/processed/evaluation_dataset.json`  ",
        "**Evaluator Script:** `scripts/run_evaluation.py`  ",
        f"**Benchmark Dataset Size:** N = {summary['dataset_size']} items  ",
        f"**Label Distribution:** {dist}  ",
        "",
        "---",
        "",
        "## 1. Executive Summary & Headline Metrics",
        "",
        "The evaluation was executed on the standardized benchmark dataset covering 5 credibility tiers without altering the production scoring algorithms.",
        "",
        "### 5-Tier Fine-Grained Classification Performance",
        "",
        f"| Metric | Score |",
        f"| :--- | :---: |",
        f"| **Overall Accuracy** | **{m5['accuracy']*100:.2f}%** |",
        f"| **Macro Precision** | **{m5['macro_precision']*100:.2f}%** |",
        f"| **Macro Recall** | **{m5['macro_recall']*100:.2f}%** |",
        f"| **Macro F1-Score** | **{m5['macro_f1']*100:.2f}%** |",
        "",
        "#### Per-Classification Breakdown (5-Tier)",
        "",
        "| Classification | Support | Precision | Recall | F1-Score |",
        "| :--- | :---: | :---: | :---: | :---: |",
    ]

    for c in classes_5:
        p = m5["per_class"][c]
        lines.append(f"| **{c}** | {p['support']} | **{p['precision']*100:.1f}%** | **{p['recall']*100:.1f}%** | **{p['f1_score']*100:.1f}%** |")

    lines.extend([
        "",
        "#### 5-Tier Confusion Matrix",
        "",
        "```",
        format_confusion_matrix(m5["confusion_matrix"], classes_5),
        "```",
        "",
        "---",
        "",
        "### 3-Tier Consolidated Classification Performance",
        "",
        f"| Metric | Score |",
        f"| :--- | :---: |",
        f"| **Overall Accuracy** | **{m3['accuracy']*100:.2f}%** |",
        f"| **Macro Precision** | **{m3['macro_precision']*100:.2f}%** |",
        f"| **Macro Recall** | **{m3['macro_recall']*100:.2f}%** |",
        f"| **Macro F1-Score** | **{m3['macro_f1']*100:.2f}%** |",
        "",
        "#### Per-Tier Breakdown (3-Tier)",
        "",
        "| Tier | Support | Precision | Recall | F1-Score |",
        "| :--- | :---: | :---: | :---: | :---: |",
    ])

    for c in classes_3:
        p = m3["per_class"][c]
        lines.append(f"| **{c}** | {p['support']} | **{p['precision']*100:.1f}%** | **{p['recall']*100:.1f}%** | **{p['f1_score']*100:.1f}%** |")

    lines.extend([
        "",
        "#### 3-Tier Confusion Matrix",
        "",
        "```",
        format_confusion_matrix(m3["confusion_matrix"], classes_3),
        "```",
        "",
        "---",
        "",
        "## 2. Module-Level Benchmarks",
        "",
        f"- **Evidence Verification Status Accuracy:** **{summary['module_benchmarks']['evidence_status_accuracy']*100:.1f}%**",
        f"- **User Behaviour Anomaly Detection Accuracy:** **{summary['module_benchmarks']['user_anomaly_accuracy']*100:.1f}%**",
        f"- **Similar Content Match Accuracy:** **{summary['module_benchmarks']['similar_content_accuracy']*100:.1f}%**",
        "",
        "## 3. Latency & Performance Profile",
        "",
        f"- **Average End-to-End API Latency:** **{summary['latencies']['avg_api_latency_ms']:.1f} ms**",
        f"- **Module Timings Breakdown:**",
    ])

    for k, v in summary["latencies"]["avg_module_timings_ms"].items():
        lines.append(f"  - `{k}`: {v:.1f} ms")

    lines.extend([
        "",
        "---",
        "",
        "## 4. Dataset Specification & Synthetic Demarcation",
        "",
        "The evaluation dataset (`datasets/processed/evaluation_dataset.json`) contains N = 15 representative items:",
        "- **Synthetic / Demo Examples**: Marked with `\"is_synthetic\": true, \"source_type\": \"synthetic\"` to test known edge conditions (e.g. extreme follower asymmetry, recycled narratives, fabricated quotes).",
        "- **Real-World Case Examples**: Marked with `\"is_synthetic\": false, \"source_type\": \"real_world_case\"` representing real social media occurrences (e.g., official NASA announcements, WHO advisories, debunked health rumors).",
        "",
        "## 5. Limitations & Future Work",
        "",
        "1. **Sample Size Scope**: N = 15 provides an essential calibration benchmark covering all 5 discrete decision bands, but larger automated corpora (e.g., 500+ items) will provide tighter confidence intervals.",
        "2. **Real-Time Fact Check API Quotas**: Google Fact Check Tools API enforces rate limits on unpaid tiers; offline mock responses ensure deterministic automated regression testing.",
        "3. **Absence of Evidence vs. Negative Evidence**: Unverified obscure statements default to 50/100 neutral baseline; benign local discussions without online fact-checks appropriately land in `PROBABLY REAL` or `UNCERTAIN` when organic user and comment signals are positive.",
        ""
    ])

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\n Successfully exported report to: {report_path}")


if __name__ == "__main__":
    run_evaluation()
