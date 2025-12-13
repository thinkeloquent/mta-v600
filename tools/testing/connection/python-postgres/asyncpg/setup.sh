#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "[asyncpg] Setting up virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo "[asyncpg] Installing dependencies..."
pip install -r requirements.txt

echo "[asyncpg] Setup complete."
