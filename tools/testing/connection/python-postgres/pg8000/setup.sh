#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "[pg8000] Setting up virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo "[pg8000] Installing dependencies..."
pip install -r requirements.txt

echo "[pg8000] Setup complete."
