# Social Guard: Python Virtual Environment Setup Guide

Follow this guide to set up an isolated Python virtual environment and run the backend.

---

## 1. Prerequisites
- **Python 3.10+** (Recommended: Python 3.11)
- **pip** (Python package installer)
- **Git**
- *(Optional for full deployment)*: PostgreSQL 14+, Tesseract OCR

---

## 2. Virtual Environment Creation & Activation

### macOS / Linux (zsh / bash)
```bash
# Navigate to the project root
cd /path/to/Social-gaurd

# Create a virtual environment named '.venv'
python3 -m venv .venv

# Activate the virtual environment
source .venv/bin/activate

# Verify python interpreter points to the virtual environment
which python
```

### Windows (PowerShell)
```powershell
# Navigate to the project root
cd C:\path\to\Social-gaurd

# Create a virtual environment named '.venv'
python -m venv .venv

# Activate the virtual environment
.\.venv\Scripts\Activate.ps1

# Verify python interpreter points to the virtual environment
where.exe python
```

---

## 3. Dependency Installation

```bash
# Upgrade pip, setuptools, and wheel
pip install --upgrade pip setuptools wheel

# Install backend dependencies
pip install -r backend/requirements.txt
```

---

## 4. Environment Configuration

```bash
# Navigate to backend directory or remain in project root
cp backend/.env.example backend/.env

# Update backend/.env with your Google Fact Check Tools API Key if available
```

---

## 5. Starting the FastAPI Development Server

```bash
# Run server from backend/ directory
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- **Interactive API Documentation (Swagger UI)**: `http://localhost:8000/docs`
- **Health Check Endpoint**: `http://localhost:8000/health`

---

## 6. Running Tests

```bash
# From the project root or backend directory
pytest backend/tests
```

---

## 7. Deactivating the Virtual Environment

When done working:
```bash
deactivate
```
