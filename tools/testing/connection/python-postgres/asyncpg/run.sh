#!/bin/bash
set -e
cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Running setup..."
    ./setup.sh
fi

source venv/bin/activate
echo "[asyncpg] Running connect.py..."
python connect.py
