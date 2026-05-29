#!/bin/bash
echo "========================================"
echo " SpotShare - Starting Backend Server"
echo "========================================"
echo ""

cd "$(dirname "$0")/backend"

echo "Installing dependencies..."
pip install -r requirements.txt --quiet

echo ""
echo "Starting SpotShare API on http://localhost:8000"
echo "Open frontend/index.html in your browser once the server starts."
echo "Press Ctrl+C to stop."
echo ""

python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
