#!/bin/bash

# AI Safety System - Server Startup Script
# This script starts the Flask web interface with proper virtual environment

cd "$(dirname "$0")"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    echo "Installing dependencies..."
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Set port (default 5001 to avoid macOS AirPlay on 5000)
PORT=${PORT:-5001}

echo "======================================================================="
echo "🛡️  AI Safety System - Modern Web Interface"
echo "======================================================================="
echo ""
echo "🌐 Starting server on http://localhost:$PORT"
echo ""
echo "📊 Available views:"
echo "   • Dashboard:  http://localhost:$PORT"
echo "   • Proposals:  http://localhost:$PORT/proposals"
echo "   • Detection:  http://localhost:$PORT/detection"
echo "   • Penalties:  http://localhost:$PORT/penalties"
echo "   • System:     http://localhost:$PORT/system"
echo "   • Config:     http://localhost:$PORT/config"
echo ""
echo "Press Ctrl+C to stop"
echo "======================================================================="
echo ""

# Run with custom port
python app.py --port $PORT
