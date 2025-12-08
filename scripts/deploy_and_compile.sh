#!/bin/bash
# Deploy code and compile C extension on all nodes
# Usage: ./scripts/deploy_and_compile.sh [node]

set -e

SSH_KEY="$HOME/.ssh/id_ed25519"
PROJECT_DIR="/home/xx/AI-Safety-System-Design"

# Cluster nodes
declare -A NODES=(
    ["novel"]="novel@192.168.0.146"
    ["page"]="page@192.168.0.168"
    ["orin"]="orin@192.168.0.160"
    ["gin"]="gin@192.168.0.242"
    ["archi"]="archi@192.168.0.232"
    ["tif"]="tif@192.168.0.213"
    ["tori"]="tori@192.168.0.235"
)

deploy_and_compile() {
    local node=$1
    local node_addr="${NODES[$node]}"
    local user=$(echo $node_addr | cut -d'@' -f1)
    local remote_dir="/home/$user/AI-Safety-System-Design"
    
    echo "========================================"
    echo "Processing $node ($node_addr)..."
    
    # 1. Deploy Code
    echo "Deploying code..."
    # Ensure remote directory exists
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$node_addr" "mkdir -p $remote_dir/communication/aura_native"

    # Sync communication module (excluding local binaries)
    rsync -avz \
        --exclude '*.so' \
        --exclude '*.o' \
        --exclude 'build/' \
        --exclude '__pycache__/' \
        -e "ssh -i $SSH_KEY -o StrictHostKeyChecking=no" \
        "$PROJECT_DIR/communication/" "${node_addr}:${remote_dir}/communication/"

    # Sync other required modules
    rsync -avz -e "ssh -i $SSH_KEY -o StrictHostKeyChecking=no" \
        "$PROJECT_DIR/utilities/" "${node_addr}:${remote_dir}/utilities/"
    rsync -avz -e "ssh -i $SSH_KEY -o StrictHostKeyChecking=no" \
        "$PROJECT_DIR/config/" "${node_addr}:${remote_dir}/config/"
    rsync -avz -e "ssh -i $SSH_KEY -o StrictHostKeyChecking=no" \
        "$PROJECT_DIR/infrastructure/" "${node_addr}:${remote_dir}/infrastructure/"
        
    echo "✓ Code deployed"
    
    # 2. Compile C Extension
    echo "Compiling C extension..."
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$node_addr" \
        "cd $remote_dir/communication/aura_native && python3 setup.py build_ext --inplace"
        
    if [ $? -eq 0 ]; then
        echo "✓ Compilation successful on $node"
    else
        echo "✗ Compilation FAILED on $node"
        exit 1
    fi
}

if [[ -n "$1" ]]; then
    if [[ -n "${NODES[$1]}" ]]; then
        deploy_and_compile "$1"
    else
        echo "Unknown node: $1"
        exit 1
    fi
else
    echo "Deploying to ALL nodes..."
    for node in "${!NODES[@]}"; do
        deploy_and_compile "$node"
    done
fi

echo "========================================"
echo "All deployments completed successfully."
