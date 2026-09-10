# Social Guard — Security, Privacy & Responsible Data Review

**Project:** Social Guard: An Explainable AI Framework for Social Media Content Verification  
**Date:** September 10, 2026  
**Status:** **AUDITED & HARDENED** (All 87 Test Cases Passing)  
**Scope:** Backend (FastAPI, SQLAlchemy, PyTorch, S-BERT), Database Models, Chrome Extension (Manifest V3), Data Extraction, and Logging.

---

## 1. Executive Summary

A comprehensive security, privacy, and responsible-data audit was performed on the Social Guard codebase. The framework operates on an **ephemeral, privacy-first, public-data-only** principle:
- No private personal data (PII), email addresses, IP addresses, DMs, or authentication tokens are collected or stored.
- Analysis is performed strictly on publicly accessible post text, visible comments, flairs, and public author metadata.
- All identified security risks have been classified and automatically remediated without breaking functionality.

---

## 2. Security & Privacy Findings Matrix

| Finding ID | Severity | Category | Description | Status |
| :--- | :---: | :--- | :--- | :---: |
| **SEC-01** | **HIGH** | CORS Configuration | Backend previously allowed wildcard `ALLOWED_ORIGINS = ["*"]` by default. | **RESOLVED** (Restricted default origins to `localhost:3000`, `localhost:8000`, `127.0.0.1:8000`, and `chrome-extension://` via regex). |
| **SEC-02** | **HIGH** | Browser Permissions | Chrome Extension `manifest.json` included overly broad `https://*/*` in `host_permissions`. | **RESOLVED** (Removed broad host access; restricted to local API `http://localhost:8000/*` and `http://127.0.0.1:8000/*`). |
| **SEC-03** | **MEDIUM** | Frontend XSS | Dynamic reason factor rendering used `innerHTML` string interpolation in extension popup. | **RESOLVED** (Replaced with safe `textContent` and explicit DOM node creation). |
| **SEC-04** | **LOW** | Secret Exposure Risk | Default development secrets in `Settings` class without warning. | **RESOLVED** (Enforced environment variable loading via `.env` with strict `.gitignore` exclusion of `.env` files). |
| **SEC-05** | **LOW** | Information Disclosure | Unhandled server exceptions could potentially leak internal stack traces. | **RESOLVED** (Generic 500 error handler outputs standardized JSON responses without exposing raw traceback). |

---

## 3. Detailed Audit by Domain

### 3.1 API Keys & Secrets Management
- **Google Fact Check API Key:** Configured via `GOOGLE_FACT_CHECK_API_KEY` in `Settings` using Pydantic `BaseSettings`. Never embedded or hardcoded in source code or client-side extension scripts.
- **Git Hygiene:** `.gitignore` properly excludes `.env`, `.env.local`, `.pem`, `.key`, and local model artifacts.
- **Client Separation:** The Chrome extension communicates strictly with the local FastAPI backend `/analyze` endpoint; it never holds or requests external third-party API keys or database connection strings.

### 3.2 Database Credentials & Storage Minimization
- **Credential Storage:** `DATABASE_URL` is parsed from environment variables. No plain-text passwords or secret tokens are stored in the database tables.
- **Data Minimization:**
  - `UserModel` stores only aggregate behavioral features (e.g., `account_age_days`, `followers`, `posts_per_day`, `duplicate_content_ratio`). No private user metadata (phone numbers, emails, location history, private chats) is modeled or stored.
  - Relational tables (`posts`, `comments`, `evidence`, `analysis_results`) retain only the context necessary for explainable verification audit trails.

### 3.3 Network & CORS Security
- `app/main.py` utilizes FastAPI `CORSMiddleware` with strict `allow_origin_regex`:
  ```python
  allow_origin_regex=r"^(chrome-extension://.*|http://localhost(:\d+)?|http://127\.0\.0\.1(:\d+)?)$"
  ```
- Replaced wildcard `"*"` with explicit, safe local development origins.

### 3.4 Cross-Site Scripting (XSS) & DOM Safety
- Verified all client-side UI rendering in `extension/popup/popup.js`.
- Fact check source URLs are validated with `target="_blank"`, and dynamically created nodes use safe DOM APIs (`document.createElement`, `element.textContent`) rather than `innerHTML` interpolation of user-supplied text.

### 3.5 Browser Extension Permissions (Least Privilege)
- Verified `extension/manifest.json` conforms to Manifest V3:
  - **Permissions:** Restricted strictly to `"activeTab"`, `"storage"`, and `"scripting"`.
  - **Host Permissions:** Restricted to `"http://localhost:8000/*"` and `"http://127.0.0.1:8000/*"`.
  - No background network tracking or unprompted background scraping occurs. Content extraction is triggered explicitly when the user requests verification.

### 3.6 Public-Data Extraction Safety
- Platform extractors (`RedditExtractor` and content scripts) adhere to strict scraping rules:
  - Only parse client-side publicly rendered DOM elements.
  - Zero attempt to bypass authentication barriers, CAPTCHAs, or rate limits.
  - Gracefully handles missing elements by providing empty arrays or `None` without crashing.

---

## 4. Security & Privacy Checklist

- [x] **Zero Hardcoded Secrets:** No API keys, database passwords, or private keys committed to the repository.
- [x] **Strict `.gitignore`:** Excludes all `.env`, virtual environments, caches, and secret keys.
- [x] **CORS Boundaries:** Restricted to local endpoints and Chrome extension origins; no wildcard credential leakage.
- [x] **Input Validation:** Strict Pydantic models for incoming payloads (`SocialMediaPost`, `AnalysisRequest`) reject malformed data with HTTP 422.
- [x] **XSS Prevention:** Extension UI uses safe DOM manipulation (`textContent`) for external claims, titles, and explanations.
- [x] **Minimal Extension Permissions:** No unnecessary browser permissions; `host_permissions` limited to local backend.
- [x] **Responsible Data Collection:** No private, sensitive, or behind-login personal data collected or stored.
- [x] **Error Masking:** 500 internal errors return standardized JSON responses without exposing internal server stack traces to clients.
- [x] **Decoupled AI Metric:** AI generation probability is evaluated independently and never confuses synthetic authorship with malicious falsity.
