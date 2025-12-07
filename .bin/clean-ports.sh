#!/bin/bash

# Script to clean all development ports (51000 and 52000)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Cleaning all development ports..."

bash "$SCRIPT_DIR/clean-port-51000.sh"
bash "$SCRIPT_DIR/clean-port-52000.sh"

echo "All ports cleaned"
