"""
Evaluation Framework Runner for Social Guard.

Executes the standardized evaluation benchmark dataset through:
1. End-to-End Credibility Verification Pipeline
2. Individual Analytical Module Benchmarks (Evidence, User Behaviour, Similar Content)
3. Performance Benchmarks (API latency, module timings, total execution time)
4. Metrics calculation: Accuracy, Precision, Recall, F1-Score, Confusion Matrix
5. Generates structured evaluation summaries and exports EVALUATION_REPORT.md.
"""

import json
import os
import sys
import time
from typing import Any, Dict, List
from unittest.mock import AsyncMock

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.modules.evidence_verification.factcheck_client import fact_check_client
from app.modules.user_behaviour.analyzer import user_behaviour_analyzer
from app.modules.similar_content.analyzer import similar_content_analyzer
from app.modules.evidence_verification.analyzer import evidence_verifier
from app.schemas.domain_models import UserProfile, SocialMediaPost


def load_dataset(dataset_path: str) -> List[Dict[str, Any]]:
    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("items", [])


def map_classification_to_ground_truth(classification: str) -> str:
    """Map 5-tier classification band to 3-class ground truth (REAL, FAKE, UNCERTAIN)."""
    if classification in ["LIKELY REAL", "PROBABLY REAL"]:
        return "REAL"
    elif classification in ["LIKELY FAKE", "PROBABLY FAKE"]:
        return "FAKE"
    else:
        return "UNCERTAIN"


def calculate_classification_metrics(y_true: List[str], y_pred: List[str], classes: List[str]):
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
            "precision": prec,
            "recall": rec,
            "f1_score": f1,
            "support": sum(matrix[c].values()),
        }

    macro_prec = sum(per_class[c]["precision"] for c in classes) / len(classes)
    macro_rec = sum(per_class[c]["recall"] for c in classes) / len(classes)
    macro_f1 = sum(per_class[c]["f1_score"] for c in classes) / len(classes)

    return {
        "accuracy": accuracy,
        "macro_precision": macro_prec,
        "macro_recall": macro_rec,
        "macro_f1": macro_f1,
        "per_class": per_class,
        "confusion_matrix": matrix,
    }


def run_evaluation():
    client = TestClient(app)
    dataset_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "datasets", "processed", "evaluation_dataset.json"))
    items = load_dataset(dataset_path)
    print(f"Loaded {len(items)} benchmark test items.")

    classes = ["REAL", "FAKE", "UNCERTAIN"]
    y_true = []
    y_pred = []
    
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

    for item in items:
        gt = item["ground_truth"]
        y_true.append(gt)

        # Set up mock fact check if configured
        if "mock_fact_check_response" in item:
            fact_check_client.search_claims = AsyncMock(return_value=item["mock_fact_check_response"])

        post_payload = {"post": item["post"]}
        
        t0 = time.perf_counter()
        resp = client.post("/analyze", json=post_payload)
        t1 = time.perf_counter()
        
        api_latencies.append((t1 - t0) * 1000.0)

        if resp.status_code == 200:
            data = resp.json()
            raw_class = data.get("classification", "UNCERTAIN")
            predicted_gt = map_classification_to_ground_truth(raw_class)
            y_pred.append(predicted_gt)

            timings = data.get("module_results", {}).get("timings_ms", {})
            for k in module_timings.keys():
                if k in timings:
                    module_timings[k].append(timings[k])

            breakdowns = data.get("module_results", {}).get("module_breakdowns", {})
            all_flags = data.get("module_results", {}).get("flags", [])

            # Record module evaluation stats
            ev_data = breakdowns.get("evidence", {})
            evidence_results.append({
                "id": item["id"],
                "expected": item.get("expected_evidence_status"),
                "actual": ev_data.get("status"),
                "match": item.get("expected_evidence_status") == ev_data.get("status"),
            })

            ub_data = breakdowns.get("user_behaviour", {})
            is_anom = "NEW_ACCOUNT_HIGH_POSTING_VELOCITY" in all_flags or ub_data.get("anomaly_score", 0.0) > 0.50
            user_behaviour_results.append({
                "id": item["id"],
                "expected_anomaly": item.get("expected_user_anomaly"),
                "actual_anomaly": is_anom,
                "match": item.get("expected_user_anomaly") == is_anom,
                "flags": all_flags,
            })

            sim_data = breakdowns.get("similarity", {})
            recycled = sim_data.get("recycled_content", False)
            similar_content_results.append({
                "id": item["id"],
                "expected_recycled": item.get("expected_recycled_content"),
                "actual_recycled": recycled,
                "match": item.get("expected_recycled_content") == recycled,
                "similarity_score": sim_data.get("similarity_score"),
            })
        else:
            y_pred.append("UNCERTAIN")

    metrics = calculate_classification_metrics(y_true, y_pred, classes)

    # Compute averages
    avg_api_latency = sum(api_latencies) / len(api_latencies) if api_latencies else 0.0
    avg_timings = {k: (sum(v) / len(v) if v else 0.0) for k, v in module_timings.items()}

    return {
        "dataset_size": len(items),
        "metrics": metrics,
        "avg_api_latency_ms": avg_api_latency,
        "avg_module_timings_ms": avg_timings,
        "evidence_results": evidence_results,
        "user_behaviour_results": user_behaviour_results,
        "similar_content_results": similar_content_results,
    }


if __name__ == "__main__":
    results = run_evaluation()
    print("\n=== EVALUATION RESULTS SUMMARY ===")
    print(json.dumps(results, indent=2))
