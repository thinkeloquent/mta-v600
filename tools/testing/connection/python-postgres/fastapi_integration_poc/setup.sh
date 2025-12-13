#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "[PoC] Setting up virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo "[PoC] Installing dependencies..."
pip install -r requirements.txt

echo "[PoC] Setup complete."
