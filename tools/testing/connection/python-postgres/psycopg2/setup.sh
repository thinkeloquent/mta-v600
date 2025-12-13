#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "[psycopg2] Setting up virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo "[psycopg2] Installing dependencies..."
pip install -r requirements.txt

echo "[psycopg2] Setup complete."
