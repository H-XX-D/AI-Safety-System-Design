#!/bin/bash
# Deploy SSH keys to nano cluster nodes and disable password auth
# Usage: ./deploy_ssh_keys.sh [deploy|verify|disable-password]

set -e

# Node definitions
declare -A NODES
NODES["GIN"]="gin@192.168.0.242"
NODES["ORIN"]="orin@192.168.0.160"
NODES["TORI"]="tori@192.168.0.235"
NODES["TIF"]="tif@192.168.0.213"
NODES["PAGEQA"]="page@192.168.0.168"
NODES["ARCHI"]="archi@192.168.0.232"
NODES["GUARD"]="guard@192.168.0.146"

PUBKEY_FILE="$HOME/.ssh/id_ed25519.pub"
PASSWORD="1"

deploy_keys() {
    echo "=== Deploying SSH Keys to Cluster ==="
    echo ""
    
    if [ ! -f "$PUBKEY_FILE" ]; then
        echo "ERROR: No public key found at $PUBKEY_FILE"
        echo "Generate one with: ssh-keygen -t ed25519"
        exit 1
    fi
    
    echo "Public key: $(cat $PUBKEY_FILE)"
    echo ""
    
    for NODE in "${!NODES[@]}"; do
        TARGET="${NODES[$NODE]}"
        echo ">>> $NODE ($TARGET)"
        
        # Create .ssh directory
        sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no "$TARGET" \
            "mkdir -p ~/.ssh && chmod 700 ~/.ssh" 2>/dev/null
        
        # Copy public key
        sshpass -p "$PASSWORD" scp -o StrictHostKeyChecking=no "$PUBKEY_FILE" \
            "$TARGET:~/.ssh/authorized_keys" 2>/dev/null
        
        # Set permissions
        sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no "$TARGET" \
            "chmod 600 ~/.ssh/authorized_keys" 2>/dev/null
        
        if [ $? -eq 0 ]; then
            echo "   ✅ Key deployed"
        else
            echo "   ❌ Failed"
        fi
    done
    
    echo ""
    echo "=== Deployment complete ==="
}

verify_keys() {
    echo "=== Verifying Key-Based SSH Access ==="
    echo ""
    
    SUCCESS=0
    FAILED=0
    
    for NODE in "${!NODES[@]}"; do
        TARGET="${NODES[$NODE]}"
        echo -n ">>> $NODE ($TARGET): "
        
        # Test key-based auth (BatchMode=yes fails if password required)
        if ssh -o BatchMode=yes -o ConnectTimeout=5 "$TARGET" "echo OK" 2>/dev/null | grep -q OK; then
            echo "✅ Key auth works"
            ((SUCCESS++))
        else
            echo "❌ Key auth failed"
            ((FAILED++))
        fi
    done
    
    echo ""
    echo "=== Results: $SUCCESS succeeded, $FAILED failed ==="
    
    if [ $FAILED -gt 0 ]; then
        return 1
    fi
}

disable_password_auth() {
    echo "=== Disabling Password Authentication ==="
    echo ""
    echo "⚠️  WARNING: This will disable password SSH login!"
    echo "    Make sure key-based auth is working first."
    echo ""
    
    # First verify all keys work
    if ! verify_keys; then
        echo ""
        echo "❌ ABORT: Not all nodes have working key auth!"
        echo "   Run '$0 deploy' first, then '$0 verify'"
        exit 1
    fi
    
    echo ""
    echo "Proceeding to disable password authentication..."
    echo ""
    
    for NODE in "${!NODES[@]}"; do
        TARGET="${NODES[$NODE]}"
        echo ">>> $NODE ($TARGET)"
        
        # Disable password auth in sshd_config
        # Need sudo, password is '1'
        ssh -o BatchMode=yes "$TARGET" "echo '$PASSWORD' | sudo -S bash -c '
            # Backup original config
            cp /etc/ssh/sshd_config /etc/ssh/sshd_config.bak
            
            # Disable password auth
            sed -i \"s/^#*PasswordAuthentication.*/PasswordAuthentication no/\" /etc/ssh/sshd_config
            sed -i \"s/^#*ChallengeResponseAuthentication.*/ChallengeResponseAuthentication no/\" /etc/ssh/sshd_config
            sed -i \"s/^#*UsePAM.*/UsePAM no/\" /etc/ssh/sshd_config
            
            # Ensure pubkey auth is enabled
            sed -i \"s/^#*PubkeyAuthentication.*/PubkeyAuthentication yes/\" /etc/ssh/sshd_config
            
            # Restart sshd
            systemctl restart sshd || service ssh restart
        '" 2>/dev/null
        
        if [ $? -eq 0 ]; then
            echo "   ✅ Password auth disabled"
        else
            echo "   ❌ Failed to disable"
        fi
    done
    
    echo ""
    echo "=== Password authentication disabled ==="
    echo ""
    echo "Testing final access..."
    verify_keys
}

show_status() {
    echo "=== SSH Authentication Status ==="
    echo ""
    
    for NODE in "${!NODES[@]}"; do
        TARGET="${NODES[$NODE]}"
        echo -n ">>> $NODE ($TARGET): "
        
        # Check if key auth works
        if ssh -o BatchMode=yes -o ConnectTimeout=5 "$TARGET" "true" 2>/dev/null; then
            # Check if password auth is disabled
            PASS_AUTH=$(ssh -o BatchMode=yes "$TARGET" "grep -E '^PasswordAuthentication' /etc/ssh/sshd_config 2>/dev/null" || echo "unknown")
            if echo "$PASS_AUTH" | grep -q "no"; then
                echo "🔒 Key-only (password disabled)"
            else
                echo "⚠️  Key works but password still enabled"
            fi
        else
            echo "❌ Key auth not working"
        fi
    done
}

# Main
case "${1:-status}" in
    deploy)
        deploy_keys
        ;;
    verify)
        verify_keys
        ;;
    disable-password|disable)
        disable_password_auth
        ;;
    status)
        show_status
        ;;
    *)
        echo "Usage: $0 {deploy|verify|disable-password|status}"
        echo ""
        echo "  deploy           - Deploy SSH keys to all nodes using password auth"
        echo "  verify           - Verify key-based SSH works on all nodes"
        echo "  disable-password - Disable password auth (requires working keys)"
        echo "  status           - Show current SSH auth status"
        exit 1
        ;;
esac
