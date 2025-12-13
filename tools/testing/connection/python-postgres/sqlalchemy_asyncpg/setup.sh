#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "[sqlalchemy_asyncpg] Setting up virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo "[sqlalchemy_asyncpg] Installing dependencies..."
pip install -r requirements.txt

echo "[sqlalchemy_asyncpg] Setup complete."
