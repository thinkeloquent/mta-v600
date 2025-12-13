#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "[psycopg3] Setting up virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo "[psycopg3] Installing dependencies..."
pip install -r requirements.txt

echo "[psycopg3] Setup complete."
