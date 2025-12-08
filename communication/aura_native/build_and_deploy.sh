#!/bin/bash
# Build and deploy AURA native extension to Orin cluster
#
# Usage:
#   ./build_and_deploy.sh          # Build locally and deploy to all nodes
#   ./build_and_deploy.sh local    # Build locally only
#   ./build_and_deploy.sh deploy   # Deploy only (assumes already built on each node)
#   ./build_and_deploy.sh orin     # Build and deploy to specific node

set -e

# Node configuration
declare -A NODES=(
    ["page"]="page@192.168.0.168"
    ["orin"]="orin@192.168.0.160"
    ["gin"]="gin@192.168.0.242"
    ["archi"]="archi@192.168.0.232"
    ["tif"]="tif@192.168.0.213"
    ["tori"]="tori@192.168.0.235"
    ["novel"]="novel@192.168.0.146"
)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
NATIVE_DIR="$PROJECT_ROOT/communication/aura_native"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

build_local() {
    log_info "Building AURA native extension locally..."
    cd "$NATIVE_DIR"
    
    # Clean previous builds
    rm -rf build/ *.so *.egg-info
    
    # Build with optimizations
    CFLAGS="-O3" python3 setup.py build_ext --inplace
    
    if [ -f aura_compress*.so ]; then
        log_info "Build successful: $(ls aura_compress*.so)"
    else
        log_error "Build failed - no .so file produced"
        exit 1
    fi
}

build_on_node() {
    local node_name=$1
    local node_addr=${NODES[$node_name]}
    
    if [ -z "$node_addr" ]; then
        log_error "Unknown node: $node_name"
        return 1
    fi
    
    log_info "Building on $node_name ($node_addr)..."
    
    # Sync source files
    ssh "$node_addr" "mkdir -p /opt/orka/aura_native"
    rsync -avz --progress \
        "$NATIVE_DIR/aura_compress.c" \
        "$NATIVE_DIR/setup.py" \
        "$node_addr:/opt/orka/aura_native/"
    
    # Build on remote with Orin-specific flags
    ssh "$node_addr" "cd /opt/orka/aura_native && \
        CFLAGS='-O3 -march=armv8.2-a+crypto' python3 setup.py build_ext --inplace"
    
    # Verify build
    if ssh "$node_addr" "ls /opt/orka/aura_native/aura_compress*.so" &>/dev/null; then
        log_info "Build successful on $node_name"
    else
        log_error "Build failed on $node_name"
        return 1
    fi
}

deploy_python_wrapper() {
    local node_addr=$1
    
    # Create Python package structure
    ssh "$node_addr" "mkdir -p /opt/orka/communication/aura_native"
    
    # Copy Python wrapper
    rsync -avz "$NATIVE_DIR/__init__.py" "$node_addr:/opt/orka/communication/aura_native/"
    
    # Create communication package init
    ssh "$node_addr" "touch /opt/orka/communication/__init__.py"
    
    # Add to PYTHONPATH in bashrc if not already there
    ssh "$node_addr" "grep -q 'PYTHONPATH.*orka' ~/.bashrc || \
        echo 'export PYTHONPATH=/opt/orka:\$PYTHONPATH' >> ~/.bashrc"
}

build_all_nodes() {
    log_info "Building on all Orin nodes..."
    
    for node_name in "${!NODES[@]}"; do
        if ping -c 1 -W 2 "${NODES[$node_name]#*@}" &>/dev/null; then
            build_on_node "$node_name"
            deploy_python_wrapper "${NODES[$node_name]}"
        else
            log_warn "Node $node_name unreachable, skipping"
        fi
    done
}

verify_deployment() {
    log_info "Verifying deployment on all nodes..."
    
    local success=0
    local total=0
    
    for node_name in "${!NODES[@]}"; do
        local node_addr=${NODES[$node_name]}
        total=$((total + 1))
        
        if ! ping -c 1 -W 2 "${node_addr#*@}" &>/dev/null; then
            log_warn "$node_name: unreachable"
            continue
        fi
        
        # Test import
        if ssh "$node_addr" "cd /opt/orka && python3 -c 'from communication.aura_native import is_native_available; print(is_native_available())'" 2>/dev/null | grep -q True; then
            log_info "$node_name: ✓ Native extension working"
            success=$((success + 1))
        else
            log_error "$node_name: ✗ Native extension not working"
        fi
    done
    
    log_info "Deployment status: $success/$total nodes operational"
}

benchmark_node() {
    local node_addr=$1
    
    log_info "Benchmarking $node_addr..."
    
    ssh "$node_addr" "cd /opt/orka && python3 -c '
import time
from communication.aura_native import compress, prewarm, is_native_available

print(f\"Native available: {is_native_available()}\")

# Prewarm
prewarm_time = prewarm(1000)
print(f\"Prewarm (1000 iterations): {prewarm_time*1000:.2f}ms\")

# Benchmark
msg = {\"priority\": 1, \"source_id\": 0, \"target_id\": 1, \"command\": \"TEST\", \"payload\": \"benchmark\"}
iterations = 10000

start = time.perf_counter()
for _ in range(iterations):
    compress(msg)
elapsed = time.perf_counter() - start

ops_per_sec = iterations / elapsed
us_per_op = (elapsed / iterations) * 1_000_000
print(f\"Throughput: {ops_per_sec:,.0f} ops/sec ({us_per_op:.2f} μs/op)\")
'"
}

# Main
case "${1:-all}" in
    local)
        build_local
        ;;
    deploy)
        verify_deployment
        ;;
    benchmark)
        for node_addr in "${NODES[@]}"; do
            benchmark_node "$node_addr"
        done
        ;;
    verify)
        verify_deployment
        ;;
    all)
        build_all_nodes
        verify_deployment
        ;;
    *)
        if [ -n "${NODES[$1]}" ]; then
            build_on_node "$1"
            deploy_python_wrapper "${NODES[$1]}"
            benchmark_node "${NODES[$1]}"
        else
            echo "Usage: $0 [local|deploy|verify|benchmark|all|<node_name>]"
            echo "Nodes: ${!NODES[*]}"
            exit 1
        fi
        ;;
esac

log_info "Done!"
