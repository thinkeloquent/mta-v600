#!/bin/bash

# Script to kill processes running on port 52000 (FastAPI)

PORT=52000

echo "Checking for processes on port $PORT..."

# Find the PID of the process using the port
PIDS=$(lsof -ti :$PORT)

if [ -z "$PIDS" ]; then
    echo "No process found running on port $PORT"
    exit 0
fi

echo "Found process(es): $PIDS"

# Kill the processes
for PID in $PIDS; do
    echo "Killing process $PID..."
    kill -9 $PID
done

echo "Port $PORT has been cleaned up successfully"
