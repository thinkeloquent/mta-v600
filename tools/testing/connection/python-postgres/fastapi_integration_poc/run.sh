#!/bin/bash
set -e
cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Running setup..."
    ./setup.sh
fi

source venv/bin/activate
echo "[PoC] Starting FastAPI server..."
# Run uvicorn pointing to app.main:app
# We assume parent dir is in pythonpath or we run as module
export PYTHONPATH=$PYTHONPATH:.
uvicorn app.main:app --reload --port 8000
