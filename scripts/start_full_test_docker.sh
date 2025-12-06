#!/bin/bash
# Run full capacity test with Docker access
# This wrapper ensures the process has docker group access

cd "$(dirname "$0")/.."

# Remove stale lock
rm -f /tmp/orkastrator_full_test.lock

# Create log directory
mkdir -p data/full_capacity_tests

# Set up log file
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="data/full_capacity_tests/full_run_${TIMESTAMP}.log"

# Build command
if [ $# -gt 0 ]; then
    RESEARCHERS="--researchers $@"
    RESEARCHER_LIST="$@"
else
    RESEARCHERS=""
    RESEARCHER_LIST="GIN ORIN TIF TORI ARCHI NOVEL"
fi

echo "============================================================"
echo "ORKASTRATOR FULL CAPACITY TEST (with Docker sandbox)"
echo "============================================================"
echo "Researchers: $RESEARCHER_LIST"
echo "Log file: $LOG_FILE"
echo "Start time: $(date)"
echo ""

# Run with Docker group access
export PYTHONUNBUFFERED=1
sg docker -c "nohup python3 scripts/run_full_capacity_test.py $RESEARCHERS > $LOG_FILE 2>&1 &"
sleep 2

# Get PID of the background process
PID=$(pgrep -f "python3 scripts/run_full_capacity_test.py" | tail -1)
echo "Started with PID: $PID"
echo ""
echo "Commands:"
echo "  Monitor:  tail -f $LOG_FILE"
echo "  Status:   ps -p $PID -o pid,etime,cmd 2>/dev/null"
echo "  Stop:     kill $PID"
echo ""

# Wait a moment and show initial output
sleep 5
if [ -f "$LOG_FILE" ]; then
    echo "Initial output:"
    echo "---------------"
    head -50 "$LOG_FILE"
fi

echo ""
echo "Test is running in background. Expected time: ~40-60 minutes for all 6 researchers."
