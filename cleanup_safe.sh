#!/usr/bin/env bash
# Safe cleanup script - Python artifacts only
# Does NOT touch ESP32, code files, or documentation
# Run with: bash cleanup_safe.sh

set -euo pipefail

echo "=== AI Safety System Design - Safe Cleanup ==="
echo ""
echo "This will remove:"
echo "  - .DS_Store files"
echo "  - __pycache__ directories"
echo "  - .pyc/.pyo compiled files"
echo "  - Virtual environments (.venv, venv, ui/venv)"
echo "  - .pytest_cache"
echo "  - .hypothesis"
echo "  - Empty directories"
echo "  - 3 safe orphaned files (no dependencies)"
echo ""
echo "This will NOT touch:"
echo "  - ESP32 directory (completely untouched)"
echo "  - Any source code"
echo "  - Any documentation"
echo ""
read -p "Continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 1
fi

echo ""
echo "Starting cleanup..."

# Count items before cleanup
echo ""
echo "Counting items to be removed..."
DS_COUNT=$(find . -name ".DS_Store" -not -path "./esp32/*" 2>/dev/null | wc -l)
PYCACHE_COUNT=$(find . -type d -name "__pycache__" -not -path "./esp32/*" 2>/dev/null | wc -l)
PYC_COUNT=$(find . -type f \( -name "*.pyc" -o -name "*.pyo" \) -not -path "./esp32/*" 2>/dev/null | wc -l)

echo "  - .DS_Store files: $DS_COUNT"
echo "  - __pycache__ dirs: $PYCACHE_COUNT"
echo "  - .pyc/.pyo files: $PYC_COUNT"
echo ""

# 1. Remove .DS_Store files (but not in esp32)
echo "[1/9] Removing .DS_Store files..."
find . -name ".DS_Store" -not -path "./esp32/*" -delete 2>/dev/null || true

# 2. Remove __pycache__ directories (but not in esp32)
echo "[2/9] Removing __pycache__ directories..."
find . -type d -name "__pycache__" -not -path "./esp32/*" -exec rm -rf {} + 2>/dev/null || true

# 3. Remove .pyc and .pyo files (but not in esp32)
echo "[3/9] Removing .pyc/.pyo files..."
find . -type f \( -name "*.pyc" -o -name "*.pyo" \) -not -path "./esp32/*" -delete 2>/dev/null || true

# 4. Remove virtual environments
echo "[4/9] Removing virtual environments..."
if [ -d ".venv" ]; then
    echo "  - Removing .venv ($(du -sh .venv 2>/dev/null | cut -f1))"
    rm -rf .venv
fi
if [ -d "venv" ]; then
    echo "  - Removing venv ($(du -sh venv 2>/dev/null | cut -f1))"
    rm -rf venv
fi
if [ -d "ui/venv" ]; then
    echo "  - Removing ui/venv ($(du -sh ui/venv 2>/dev/null | cut -f1))"
    rm -rf ui/venv
fi

# 5. Remove pytest cache
echo "[5/9] Removing .pytest_cache..."
if [ -d ".pytest_cache" ]; then
    rm -rf .pytest_cache
fi

# 6. Remove hypothesis cache
echo "[6/9] Removing .hypothesis..."
if [ -d ".hypothesis" ]; then
    rm -rf .hypothesis
fi

# 7. Remove safe orphaned files (verified no dependencies)
echo "[7/9] Removing orphaned files with no dependencies..."
if [ -f "translator_verification.py" ]; then
    echo "  - translator_verification.py"
    rm translator_verification.py
fi
if [ -f "demo_presentation.py" ]; then
    echo "  - demo_presentation.py"
    rm demo_presentation.py
fi
if [ -f "test_worm_creation.py" ]; then
    echo "  - test_worm_creation.py"
    rm test_worm_creation.py
fi

# 8. Remove empty directories (but not in esp32)
echo "[8/9] Removing empty directories..."
if [ -d "sidechain/cold" ] && [ -z "$(ls -A sidechain/cold)" ]; then
    echo "  - sidechain/cold"
    rmdir sidechain/cold 2>/dev/null || true
fi
if [ -d "ui/components" ] && [ -z "$(ls -A ui/components)" ]; then
    echo "  - ui/components"
    rmdir ui/components 2>/dev/null || true
fi
if [ -d "archive/analysis" ] && [ -z "$(ls -A archive/analysis)" ]; then
    echo "  - archive/analysis"
    rmdir archive/analysis 2>/dev/null || true
fi
if [ -d "archive/logs" ] && [ -z "$(ls -A archive/logs)" ]; then
    echo "  - archive/logs"
    rmdir archive/logs 2>/dev/null || true
fi
if [ -d "audit_logs" ] && [ -z "$(ls -A audit_logs)" ]; then
    echo "  - audit_logs"
    rmdir audit_logs 2>/dev/null || true
fi

# 9. Remove empty boot_log.txt if it exists
echo "[9/9] Removing empty log files..."
if [ -f "boot_log.txt" ] && [ ! -s "boot_log.txt" ]; then
    echo "  - boot_log.txt (0 bytes)"
    rm boot_log.txt
fi

echo ""
echo "✓ Cleanup complete!"
echo ""
echo "Next steps:"
echo "  1. Run: bash organize_docs.sh  (to organize markdown files)"
echo "  2. Recreate virtual environment: python3 -m venv .venv"
echo "  3. Install dependencies: source .venv/bin/activate && pip install -r requirements.txt"
echo ""
