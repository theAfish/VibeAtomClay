#!/bin/bash

# Exit on error
set -e

echo "Starting VibeAtomClay Setup..."

# Check for Python
if command -v python3 &> /dev/null; then
    PYTHON_CMD=python3
elif command -v python &> /dev/null; then
    PYTHON_CMD=python
else
    echo "Error: Python is not installed or not in your PATH."
    exit 1
fi

echo "Using Python: $($PYTHON_CMD --version)"

# Run the Python setup script
$PYTHON_CMD setup_dev.py

echo ""
echo "Setup finished successfully!"
