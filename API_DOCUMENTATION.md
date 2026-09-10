# Social Guard: REST API Specification

**Project:** Social Guard: An Explainable AI Framework for Social Media Content Verification  
**Document:** API_DOCUMENTATION.md  
**Base URL:** `http://127.0.0.1:8000` (Local) / `http://localhost:8000`  
**API Prefix:** `/api/v1` (or root aliases)  
**OpenAPI Swagger Docs:** `http://127.0.0.1:8000/docs`

---

## 1. Health Check Endpoint

### `GET /health`
Returns the operational health of the Social Guard backend service.

#### Request
```http
GET /health HTTP/1.1
Host: 127.0.0.1:8000
```

#### Response (`HTTP 200 OK`)
```json
{
  "status": "ok",
  "service": "social-guard",
  "version": "0.1.0"
}
```

---

## 2. Content Verification Endpoint

### `POST /analyze`
Performs end-to-end multi-modal Explainable AI credibility analysis.

#### Request Headers
```http
Content-Type: application/json
```

#### Request Body (`AnalysisRequest`)
```json
{
  "request_id": "sg_req_sample_01",
  "post": {
    "platform": "twitter",
    "text": "NASA rovers confirm detection of water ice reserves beneath Martian surface during deep radar soundings.",
    "hashtags": ["#Space", "#Mars", "#NASA"],
    "media": [
      {
        "url": "https://example.com/mars_chart.png",
        "media_type": "image"
      }
    ],
    "timestamp": "2026-09-10T09:00:00Z",
    "author": {
      "username": "science_reporter",
      "account_age_days": 1200,
      "followers": 15000,
      "following": 450,
      "posts_per_day": 2.5,
      "comments_per_day": 4.0,
      "engagement_rate": 0.045,
      "duplicate_content_ratio": 0.01,
      "hashtag_repetition_rate": 0.10
    },
    "comments": [
      {
        "comment_id": "c_1",
        "text": "Fascinating data! Does this correlate with earlier orbital radar measurements?",
        "timestamp": "2026-09-10T09:10:00Z",
        "likes": 5,
        "emojis": ["🚀"]
      }
    ]
  },
  "custom_weights": {
    "comments": 0.20,
    "evidence": 0.40,
    "user_behaviour": 0.15,
    "similar_content": 0.25
  }
}
```

#### Response (`HTTP 200 OK` — `FinalAnalysisResult`)
```json
{
  "request_id": "sg_req_sample_01",
  "consolidated_score": 84.50,
  "classification": "LIKELY REAL",
  "ai_generation_probability": 0.18,
  "explanation": "This post is classified as LIKELY REAL based on high factual evidence and mature user behaviour.",
  "module_scores": {
    "comment_analysis": 80.0,
    "evidence_verification": 100.0,
    "user_behaviour": 88.0,
    "similar_content": 85.0
  },
  "module_results": {
    "timings_ms": {
      "comment_analysis_ms": 12.4,
      "evidence_verification_ms": 0.2,
      "user_behaviour_ms": 8.1,
      "similar_content_ms": 22.5,
      "score_fusion_ms": 0.04,
      "total_pipeline_ms": 45.2
    },
    "module_breakdowns": {
      "comments": { "score": 80.0, "metrics": { "duplicate_ratio": 0.0 } },
      "evidence": { "status": "SUPPORTED", "fact_checks": [ { "publisher": "Reuters Fact Check", "rating_category": "TRUE" } ] },
      "user_behaviour": { "score": 88.0, "anomaly_score": 0.12 },
      "similarity": { "score": 85.0, "recycled_content": false }
    },
    "explainability": {
      "summary": "This post is classified as LIKELY REAL.",
      "positive_factors": [
        { "module": "evidence", "factor": "Verified by credible fact-checking sources" }
      ],
      "negative_factors": []
    },
    "flags": ["VERIFIED_BY_FACT_CHECKERS"]
  },
  "created_at": "2026-09-10T09:00:05.123456Z"
}
```

---

## 3. Error Responses

| Status Code | Error Reason | Example Response Body |
| :---: | :--- | :--- |
| **HTTP 422** | Unprocessable Content (Schema validation failed) | `{"error": "ValidationError", "message": "The incoming payload failed schema validation.", "details": [...]}` |
| **HTTP 500** | Internal Server Error (Unexpected unhandled exception) | `{"error": "InternalServerError", "message": "An unexpected error occurred during processing."}` |
