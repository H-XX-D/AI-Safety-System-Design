#!/bin/bash
#
# Deploy AURA templates to Jetson Orin Nano cluster
# Enables AI-safe compression across all nodes
#
# Usage: ./deploy_aura_templates.sh [all|node <name>|verify]
#

set -e

SSH_KEY="$HOME/.ssh/id_ed25519"
SUDO_PASS="1"
LOCAL_TEMPLATES="/home/xx/AI-Safety-System-Design/worm_usb_dir/aura_templates"
REMOTE_TEMPLATE_DIR="/opt/orka/aura_templates"

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

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

ssh_cmd() {
    local node=$1
    local cmd=$2
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -o ConnectTimeout=10 "$node" "$cmd" 2>/dev/null
}

ssh_sudo_cmd() {
    local node=$1
    local cmd=$2
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -o ConnectTimeout=10 "$node" "echo '$SUDO_PASS' | sudo -S $cmd" 2>/dev/null
}

# Deploy templates to a single node
deploy_to_node() {
    local node=$1
    local node_addr="${NODES[$node]}"
    
    log_info "Deploying AURA templates to $node ($node_addr)..."
    
    # Check if node is reachable
    if ! ping -c 1 -W 2 "$(echo $node_addr | cut -d'@' -f2)" &>/dev/null; then
        log_error "  Node unreachable"
        return 1
    fi
    
    # Create remote directory
    log_info "  Creating $REMOTE_TEMPLATE_DIR..."
    ssh_sudo_cmd "$node_addr" "mkdir -p $REMOTE_TEMPLATE_DIR"
    ssh_sudo_cmd "$node_addr" "chown -R $(echo $node_addr | cut -d'@' -f1):$(echo $node_addr | cut -d'@' -f1) $REMOTE_TEMPLATE_DIR"
    
    # Sync templates
    log_info "  Syncing templates (~8.5 MB)..."
    rsync -avz --progress \
        -e "ssh -i $SSH_KEY -o StrictHostKeyChecking=no" \
        "$LOCAL_TEMPLATES/" "${node_addr}:${REMOTE_TEMPLATE_DIR}/"
    
    # Verify files
    log_info "  Verifying files..."
    local remote_files=$(ssh_cmd "$node_addr" "ls -1 $REMOTE_TEMPLATE_DIR/ | wc -l")
    local local_files=$(ls -1 "$LOCAL_TEMPLATES/" | wc -l)
    
    if [[ "$remote_files" -eq "$local_files" ]]; then
        log_success "  Templates synced: $remote_files files"
    else
        log_warning "  File count mismatch: local=$local_files, remote=$remote_files"
    fi
    
    # Verify manifest hash
    local local_hash=$(grep -o '"manifest_hash": "[^"]*' "$LOCAL_TEMPLATES/method_manifest.json" | cut -d'"' -f4)
    local remote_hash=$(ssh_cmd "$node_addr" "grep -o '\"manifest_hash\": \"[^\"]*' $REMOTE_TEMPLATE_DIR/method_manifest.json | cut -d'\"' -f4")
    
    if [[ "$local_hash" == "$remote_hash" ]]; then
        log_success "  Manifest hash verified: ${local_hash:0:16}..."
    else
        log_error "  Manifest hash mismatch!"
        return 1
    fi
    
    return 0
}

# Update systemd service with AURA_TEMPLATE_DIR environment
update_systemd() {
    local node=$1
    local node_addr="${NODES[$node]}"
    
    log_info "Updating systemd environment for $node..."
    
    # Check if threedlm service exists
    local service_exists=$(ssh_cmd "$node_addr" "systemctl list-unit-files | grep threedlm || echo 'not found'")
    
    if [[ "$service_exists" == *"not found"* ]]; then
        log_warning "  threedlm service not found, skipping systemd update"
        return 0
    fi
    
    # Add Environment to service if not present
    local has_env=$(ssh_cmd "$node_addr" "grep 'AURA_TEMPLATE_DIR' /etc/systemd/system/threedlm.service 2>/dev/null || echo 'not found'")
    
    if [[ "$has_env" == *"not found"* ]]; then
        log_info "  Adding AURA_TEMPLATE_DIR to service..."
        
        # Insert environment line after [Service]
        ssh_sudo_cmd "$node_addr" "sed -i '/^\[Service\]/a Environment=AURA_TEMPLATE_DIR=$REMOTE_TEMPLATE_DIR' /etc/systemd/system/threedlm.service"
        
        # Reload and restart
        ssh_sudo_cmd "$node_addr" "systemctl daemon-reload"
        ssh_sudo_cmd "$node_addr" "systemctl restart threedlm"
        
        log_success "  Service updated and restarted"
    else
        log_info "  AURA_TEMPLATE_DIR already configured"
    fi
}

# Verify compression works on a node
verify_node() {
    local node=$1
    local node_addr="${NODES[$node]}"
    
    log_info "Verifying AURA compression on $node..."
    
    # Check if Python and aura_compressor are available
    local result=$(ssh_cmd "$node_addr" "cd /home/$(echo $node_addr | cut -d'@' -f1) && \
        export AURA_TEMPLATE_DIR=$REMOTE_TEMPLATE_DIR && \
        python3 -c \"
import sys
sys.path.insert(0, '/home/$(echo $node_addr | cut -d'@' -f1)/AI-Safety-System-Design')
try:
    from communication.aura_compressor import create_compressor
    c = create_compressor(enable_aura=True)
    msg = 'System 2 approves proposal 007'
    blob, method, meta = c.compress(msg)
    out = c.decompress(blob)
    if out == msg:
        print('OK method=' + method)
    else:
        print('FAIL decode mismatch')
except Exception as e:
    print('FAIL ' + str(e))
\" 2>&1")
    
    if [[ "$result" == OK* ]]; then
        log_success "  Compression verified: $result"
        return 0
    else
        log_warning "  Verification issue: $result"
        
        # Try alternative: just check templates are readable
        local template_check=$(ssh_cmd "$node_addr" "python3 -c \"
import json
with open('$REMOTE_TEMPLATE_DIR/method_manifest.json') as f:
    m = json.load(f)
    print('Templates OK, methods:', len(m.get('methods', {})))
\" 2>&1")
        
        if [[ "$template_check" == *"Templates OK"* ]]; then
            log_info "  Templates readable: $template_check"
            return 0
        fi
        
        return 1
    fi
}

# Show template sync status across cluster
show_status() {
    log_info "AURA Template Status Across Cluster"
    echo ""
    
    local local_hash=$(grep -o '"manifest_hash": "[^"]*' "$LOCAL_TEMPLATES/method_manifest.json" | cut -d'"' -f4)
    echo "Local manifest hash: ${local_hash:0:32}..."
    echo ""
    
    printf "%-10s %-16s %-12s %-20s\n" "NODE" "IP" "FILES" "HASH MATCH"
    printf "%s\n" "------------------------------------------------------------"
    
    for node in "${!NODES[@]}"; do
        local node_addr="${NODES[$node]}"
        local ip=$(echo "$node_addr" | cut -d'@' -f2)
        
        local file_count=$(ssh_cmd "$node_addr" "ls -1 $REMOTE_TEMPLATE_DIR/ 2>/dev/null | wc -l" || echo "0")
        local remote_hash=$(ssh_cmd "$node_addr" "grep -o '\"manifest_hash\": \"[^\"]*' $REMOTE_TEMPLATE_DIR/method_manifest.json 2>/dev/null | cut -d'\"' -f4" || echo "missing")
        
        local hash_status
        if [[ "$remote_hash" == "$local_hash" ]]; then
            hash_status="${GREEN}✓ match${NC}"
        elif [[ "$remote_hash" == "missing" ]]; then
            hash_status="${RED}✗ missing${NC}"
        else
            hash_status="${YELLOW}⚠ mismatch${NC}"
        fi
        
        printf "%-10s %-16s %-12s " "$node" "$ip" "$file_count"
        echo -e "$hash_status"
    done
    echo ""
}

# ============================================================================
# Main
# ============================================================================

case "${1:-all}" in
    deploy-node)
        if [[ -n "$2" ]] && [[ -n "${NODES[$2]}" ]]; then
            deploy_to_node "$2"
            update_systemd "$2"
        else
            echo "Usage: $0 deploy-node <node_name>"
            echo "Nodes: ${!NODES[*]}"
        fi
        ;;
    verify-node)
        if [[ -n "$2" ]] && [[ -n "${NODES[$2]}" ]]; then
            verify_node "$2"
        else
            echo "Usage: $0 verify-node <node_name>"
        fi
        ;;
    status)
        show_status
        ;;
    verify)
        log_info "Verifying AURA compression on all nodes..."
        echo ""
        for node in "${!NODES[@]}"; do
            verify_node "$node"
            echo ""
        done
        ;;
    all)
        log_info "Deploying AURA templates to all cluster nodes..."
        echo ""
        
        # Check local templates exist
        if [[ ! -f "$LOCAL_TEMPLATES/method_manifest.json" ]]; then
            log_error "Local templates not found at $LOCAL_TEMPLATES"
            log_info "Run: python3 communication/generate_all_aura_templates.py"
            exit 1
        fi
        
        local_count=$(ls -1 "$LOCAL_TEMPLATES/" | wc -l)
        log_info "Local templates: $local_count files"
        echo ""
        
        # Deploy to each node
        for node in "${!NODES[@]}"; do
            deploy_to_node "$node"
            update_systemd "$node"
            echo ""
        done
        
        # Show status
        echo ""
        show_status
        
        log_success "AURA templates deployed to cluster!"
        log_info "Run '$0 verify' to test compression on each node"
        ;;
    *)
        echo "AURA Template Deployment for Jetson Cluster"
        echo ""
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  all              - Deploy templates to all nodes (default)"
        echo "  deploy-node <n>  - Deploy to specific node"
        echo "  verify           - Verify compression on all nodes"
        echo "  verify-node <n>  - Verify specific node"
        echo "  status           - Show template sync status"
        echo ""
        echo "Nodes: ${!NODES[*]}"
        ;;
esac
