#!/bin/bash
# ============================================================================
# ORKASTRATOR UI Launch Script
# ============================================================================
# Simple, reliable launcher for the ORKASTRATOR web interface
# ============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UI_DIR="$SCRIPT_DIR/ui"
PORT="${1:-5001}"
LOG_FILE="$SCRIPT_DIR/logs/ui.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║                    🎯 ORKASTRATOR UI LAUNCHER                        ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check if UI directory exists
if [ ! -d "$UI_DIR" ]; then
    echo -e "${RED}Error: UI directory not found at $UI_DIR${NC}"
    exit 1
fi

# Check if app.py exists
if [ ! -f "$UI_DIR/app.py" ]; then
    echo -e "${RED}Error: app.py not found in $UI_DIR${NC}"
    exit 1
fi

# Create logs directory if needed
mkdir -p "$SCRIPT_DIR/logs"

# Kill any existing UI processes on this port
echo -e "${YELLOW}Checking for existing processes on port $PORT...${NC}"
EXISTING_PID=$(lsof -ti:$PORT 2>/dev/null || true)
if [ -n "$EXISTING_PID" ]; then
    echo -e "${YELLOW}Killing existing process on port $PORT (PID: $EXISTING_PID)${NC}"
    kill -9 $EXISTING_PID 2>/dev/null || true
    sleep 1
fi

# Also kill any zombie python3 app.py processes
pkill -f "python3 app.py" 2>/dev/null || true
pkill -f "python3.*app.py" 2>/dev/null || true
sleep 1

# Set environment variables
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"
export FLASK_APP="app.py"
export FLASK_ENV="development"

# Change to UI directory
cd "$UI_DIR"

echo -e "${GREEN}Starting ORKASTRATOR UI on port $PORT...${NC}"
echo ""

# Run with nohup in background
nohup python3 app.py --port "$PORT" --host 0.0.0.0 > "$LOG_FILE" 2>&1 &
UI_PID=$!

# Save PID for later
echo $UI_PID > "$SCRIPT_DIR/ui.pid"

# Wait for startup
echo -e "${BLUE}Waiting for server to start...${NC}"
for i in {1..15}; do
    sleep 1
    if curl -s http://localhost:$PORT/api/health > /dev/null 2>&1; then
        echo ""
        echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║                    ✅ ORKASTRATOR UI STARTED                         ║${NC}"
        echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════════╝${NC}"
        echo ""
        echo -e "${CYAN}🌐 Access the UI at:${NC}"
        echo -e "   ${GREEN}http://localhost:$PORT${NC}"
        echo -e "   ${GREEN}http://$(hostname -I | awk '{print $1}'):$PORT${NC}"
        echo ""
        echo -e "${CYAN}📊 Available views:${NC}"
        echo -e "   • Dashboard:  http://localhost:$PORT"
        echo -e "   • Proposals:  http://localhost:$PORT/proposals"
        echo -e "   • Detection:  http://localhost:$PORT/detection"
        echo -e "   • ORKA:       http://localhost:$PORT/orka"
        echo -e "   • System:     http://localhost:$PORT/system"
        echo ""
        echo -e "${YELLOW}📝 Logs: $LOG_FILE${NC}"
        echo -e "${YELLOW}🔄 PID: $UI_PID${NC}"
        echo ""
        echo -e "${CYAN}To stop: kill $UI_PID${NC}"
        exit 0
    fi
    echo -n "."
done

# If we get here, startup failed
echo ""
echo -e "${RED}Server failed to start within 15 seconds${NC}"
echo -e "${YELLOW}Check logs: $LOG_FILE${NC}"
echo ""
echo -e "${YELLOW}Last 30 lines of log:${NC}"
tail -30 "$LOG_FILE" 2>/dev/null || echo "No log file found"
exit 1
