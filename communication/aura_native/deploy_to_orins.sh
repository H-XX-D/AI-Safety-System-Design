#!/bin/bash
# Deploy AURA native extension updates to all Orin nodes
# Run this when nodes are online

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMM_DIR="$(dirname "$SCRIPT_DIR")"

# Orin node IPs (from deploy_aura_templates.sh)
NODES=(
    "orin@192.168.0.160"   # orin
    "gin@192.168.0.242"    # gin  
    "archi@192.168.0.232"  # archi
    "tif@192.168.0.213"    # tif
    "tori@192.168.0.235"   # tori
    "novel@192.168.0.146"  # novel
    "page@192.168.0.168"   # page
)

# Files to deploy
FILES=(
    "$SCRIPT_DIR/setup.py"
    "$SCRIPT_DIR/aura_compress.c"
    "$SCRIPT_DIR/__init__.py"
    "$SCRIPT_DIR/cpu_affinity.sh"
    "$COMM_DIR/aura_ring_decoder.py"
)

echo "=== AURA Native Extension Deployment ==="
echo ""

for node in "${NODES[@]}"; do
    host="${node#*@}"
    user="${node%@*}"
    
    echo "--- Checking $user@$host ---"
    if ping -c 1 -W 1 "$host" > /dev/null 2>&1; then
        echo "  Node online, deploying..."
        
        # Copy files
        for file in "${FILES[@]}"; do
            if [ -f "$file" ]; then
                scp -o ConnectTimeout=5 "$file" "$node:~/aura_native/" 2>/dev/null && \
                    echo "  ✓ $(basename "$file")" || \
                    echo "  ✗ $(basename "$file") failed"
            fi
        done
        
        # Rebuild with optimized flags
        echo "  Rebuilding C extension..."
        ssh -o ConnectTimeout=5 "$node" "cd ~/aura_native && \
            gcc -O3 -march=armv8.2-a+crypto -mtune=cortex-a78ae -ffast-math -fPIC \
                -shared -o aura_compress.cpython-310-aarch64-linux-gnu.so \
                aura_compress.c -I/usr/include/python3.10 2>&1" && \
            echo "  ✓ Build successful" || \
            echo "  ✗ Build failed"
        
        echo ""
    else
        echo "  Node offline, skipping"
        echo ""
    fi
done

echo "=== Deployment Complete ==="
