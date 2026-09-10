#!/usr/bin/env bash
# Development script: Run code linters and checks
set -e

echo "Running code formatters and linters..."
flake8 backend/app backend/tests --count --select=E9,F63,F7,F82 --show-source --statistics
echo "Lint checks passed."
