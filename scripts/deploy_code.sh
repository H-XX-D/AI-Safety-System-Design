
#!/bin/bash
# Deploy code changes to the cluster
# Usage: ./deploy_code.sh [node]

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

deploy_to_node() {
    local node=$1
    local node_addr="${NODES[$node]}"
    local user=$(echo $node_addr | cut -d'@' -f1)
    local remote_dir="/home/$user/AI-Safety-System-Design"
    
    echo "Deploying code to $node ($node_addr)..."
    
    # Ensure remote directory exists
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$node_addr" "mkdir -p $remote_dir/communication $remote_dir/tools"

    # Sync communication module
    rsync -avz --progress \
        -e "ssh -i $SSH_KEY -o StrictHostKeyChecking=no" \
        "$PROJECT_DIR/communication/" "${node_addr}:${remote_dir}/communication/"
        
    # Sync tools (optional, but good for debugging)
    rsync -avz --progress \
        -e "ssh -i $SSH_KEY -o StrictHostKeyChecking=no" \
        "$PROJECT_DIR/tools/" "${node_addr}:${remote_dir}/tools/"
        
    echo "✓ Code deployed to $node"
}

if [[ -n "$1" ]]; then
    if [[ -n "${NODES[$1]}" ]]; then
        deploy_to_node "$1"
    else
        echo "Unknown node: $1"
        exit 1
    fi
else
    echo "Deploying to ALL nodes..."
    for node in "${!NODES[@]}"; do
        deploy_to_node "$node"
    done
fi
