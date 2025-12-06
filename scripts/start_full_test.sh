#!/bin/bash
# Start full capacity test in background with proper detachment
# Usage: ./start_full_test.sh [researchers...]
#
# Example:
#   ./start_full_test.sh           # All 6 researchers
#   ./start_full_test.sh GIN ORIN  # Just GIN and ORIN
#
# The 6 researchers:
#   GIN, ORIN, TIF - deepseek-r1:1.5b
#   TORI - gemma3:4b
#   ARCHI - qwen2.5:3b
#   NOVEL - gemma:2b (formerly guard node)
#
# System nodes (not researchers):
#   ORKA - orchestrator + guard model
#   PAGEQA - literature search/validation

set -e

cd "$(dirname "$0")/.."

# Remove stale lock
rm -f /tmp/orkastrator_full_test.lock

# Create log directory
mkdir -p data/full_capacity_tests

# Set up log file
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="data/full_capacity_tests/full_run_${TIMESTAMP}.log"
PID_FILE="data/full_capacity_tests/full_run_${TIMESTAMP}.pid"

# Build command
if [ $# -gt 0 ]; then
    RESEARCHERS="--researchers $@"
    RESEARCHER_LIST="$@"
else
    RESEARCHERS=""
    RESEARCHER_LIST="GIN ORIN TIF TORI ARCHI NOVEL"
fi

echo "============================================================"
echo "ORKASTRATOR FULL CAPACITY TEST"
echo "============================================================"
echo "Researchers: $RESEARCHER_LIST"
echo "Log file: $LOG_FILE"
echo "Start time: $(date)"
echo ""

# Run with proper unbuffering via PYTHONUNBUFFERED
export PYTHONUNBUFFERED=1
nohup python3 scripts/run_full_capacity_test.py $RESEARCHERS > "$LOG_FILE" 2>&1 &
PID=$!
echo $PID > "$PID_FILE"

echo "Started with PID: $PID"
echo ""
echo "Commands:"
echo "  Monitor:  tail -f $LOG_FILE"
echo "  Status:   ps -p $PID -o pid,etime,cmd"
echo "  Stop:     kill $PID"
echo ""

# Wait a moment and show initial output
sleep 5
if [ -f "$LOG_FILE" ]; then
    echo "Initial output:"
    echo "---------------"
    head -40 "$LOG_FILE"
fi

echo ""
echo "Test is running in background. Expected time: ~40-60 minutes for all 6 researchers."
