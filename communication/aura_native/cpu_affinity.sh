#!/bin/bash
# CPU Affinity and Priority Configuration for AURA Compression Workers
#
# Jetson Orin Nano has 6 ARM Cortex-A78AE cores (all identical, no big.LITTLE)
# Cores 4-5 recommended for compression to avoid contention with system tasks
#
# Usage:
#   ./cpu_affinity.sh <pid>           # Apply to specific process
#   ./cpu_affinity.sh --service       # Apply to threedlm-serve service
#   ./cpu_affinity.sh --setup         # Setup cgroups for auto-application
#   ./cpu_affinity.sh --tmpfs         # Setup tmpfs for compressed blobs

set -e

# Configuration for Orin Nano
COMPRESSION_CORES="4-5"       # Cores for compression/tokenization
INFERENCE_CORES="0-3"         # Cores for model inference  
NICE_PRIORITY="-5"            # Slightly elevated priority (-20 to 19)
SCHED_POLICY="SCHED_FIFO"     # Real-time scheduling (optional)
SCHED_PRIORITY="50"           # RT priority (1-99)
TMPFS_PATH="/dev/shm/aura_blobs"
TMPFS_SIZE="64M"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

apply_affinity() {
    local pid=$1
    local cores=${2:-$COMPRESSION_CORES}
    
    if [ ! -d "/proc/$pid" ]; then
        log_error "Process $pid not found"
        return 1
    fi
    
    log_info "Setting CPU affinity for PID $pid to cores $cores"
    
    # Set CPU affinity
    taskset -pc "$cores" "$pid" 2>/dev/null || {
        log_warn "taskset failed, trying cgroups"
        echo "$pid" > /sys/fs/cgroup/cpuset/aura_compress/tasks 2>/dev/null || true
    }
    
    # Set nice priority (requires root for negative values)
    if [ "$(id -u)" -eq 0 ]; then
        renice "$NICE_PRIORITY" -p "$pid" 2>/dev/null || true
        log_info "Set nice priority to $NICE_PRIORITY"
    else
        log_warn "Run as root to set nice priority"
    fi
}

apply_rt_scheduling() {
    local pid=$1
    
    if [ "$(id -u)" -ne 0 ]; then
        log_warn "Real-time scheduling requires root"
        return 1
    fi
    
    log_info "Setting real-time scheduling for PID $pid"
    chrt -f -p "$SCHED_PRIORITY" "$pid" 2>/dev/null || {
        log_warn "Could not set RT scheduling (may need kernel config)"
    }
}

setup_tmpfs() {
    log_info "Setting up tmpfs for AURA compressed blobs..."
    
    # Check if /dev/shm exists (standard on Linux)
    if [ ! -d "/dev/shm" ]; then
        log_error "/dev/shm not available"
        return 1
    fi
    
    # Create AURA blob directory
    mkdir -p "$TMPFS_PATH"
    chmod 755 "$TMPFS_PATH"
    
    # Set size limit via cgroup (if available)
    if [ "$(id -u)" -eq 0 ]; then
        # Optionally mount dedicated tmpfs
        if ! mountpoint -q "$TMPFS_PATH" 2>/dev/null; then
            mount -t tmpfs -o size=$TMPFS_SIZE,mode=755 tmpfs "$TMPFS_PATH" 2>/dev/null || true
        fi
    fi
    
    log_info "tmpfs ready at $TMPFS_PATH (size: $TMPFS_SIZE)"
    log_info "Set AURA_TMPFS_PATH=$TMPFS_PATH in your environment"
}

setup_cgroups() {
    if [ "$(id -u)" -ne 0 ]; then
        log_error "Cgroup setup requires root"
        exit 1
    fi
    
    log_info "Setting up cgroups for AURA compression..."
    
    # Create cpuset cgroup
    mkdir -p /sys/fs/cgroup/cpuset/aura_compress
    
    # Assign compression cores
    echo "$COMPRESSION_CORES" > /sys/fs/cgroup/cpuset/aura_compress/cpuset.cpus
    echo "0" > /sys/fs/cgroup/cpuset/aura_compress/cpuset.mems
    
    # Enable exclusive access (optional)
    # echo "1" > /sys/fs/cgroup/cpuset/aura_compress/cpuset.cpu_exclusive
    
    log_info "Cgroup 'aura_compress' created with cores $COMPRESSION_CORES"
    log_info "Add processes with: echo <pid> > /sys/fs/cgroup/cpuset/aura_compress/tasks"
}

find_threedlm_pids() {
    pgrep -f "threedlm-serve\|threedlm_serve\|aura_compress" 2>/dev/null || true
}

apply_to_service() {
    local pids=$(find_threedlm_pids)
    
    if [ -z "$pids" ]; then
        log_warn "No threedlm-serve processes found"
        return 1
    fi
    
    log_info "Found processes: $pids"
    
    for pid in $pids; do
        apply_affinity "$pid"
    done
}

show_current_affinity() {
    local pids=$(find_threedlm_pids)
    
    if [ -z "$pids" ]; then
        log_warn "No threedlm-serve processes found"
        return
    fi
    
    for pid in $pids; do
        local comm=$(cat /proc/$pid/comm 2>/dev/null || echo "unknown")
        local affinity=$(taskset -pc "$pid" 2>/dev/null | grep -oP "current affinity list: \K.*" || echo "unknown")
        local nice=$(ps -o ni= -p "$pid" 2>/dev/null | tr -d ' ')
        
        log_info "PID $pid ($comm): cores=$affinity nice=$nice"
    done
}

create_systemd_override() {
    if [ "$(id -u)" -ne 0 ]; then
        log_error "Systemd override requires root"
        exit 1
    fi
    
    local service_name="threedlm-serve"
    local override_dir="/etc/systemd/system/${service_name}.service.d"
    
    mkdir -p "$override_dir"
    
    cat > "$override_dir/cpu-affinity.conf" << EOF
[Service]
# AURA compression CPU affinity
CPUAffinity=$BIG_CORES
Nice=$NICE_PRIORITY
# Optional: Real-time priority
# CPUSchedulingPolicy=fifo
# CPUSchedulingPriority=$SCHED_PRIORITY
EOF
    
    log_info "Created systemd override at $override_dir/cpu-affinity.conf"
    log_info "Run: systemctl daemon-reload && systemctl restart $service_name"
}

# Parse command line
case "${1:-}" in
    --setup)
        setup_cgroups
        ;;
    --service)
        apply_to_service
        ;;
    --status)
        show_current_affinity
        ;;
    --systemd)
        create_systemd_override
        ;;
    --rt)
        if [ -z "$2" ]; then
            log_error "Usage: $0 --rt <pid>"
            exit 1
        fi
        apply_rt_scheduling "$2"
        ;;
    --help|-h)
        echo "Usage: $0 [option]"
        echo ""
        echo "Options:"
        echo "  <pid>        Apply affinity to specific process"
        echo "  --service    Apply to threedlm-serve processes"
        echo "  --status     Show current affinity of service"
        echo "  --setup      Setup cgroups (requires root)"
        echo "  --systemd    Create systemd override (requires root)"
        echo "  --rt <pid>   Apply real-time scheduling (requires root)"
        echo ""
        echo "Configuration:"
        echo "  Big cores: $BIG_CORES"
        echo "  Nice: $NICE_PRIORITY"
        ;;
    "")
        show_current_affinity
        ;;
    *)
        # Assume it's a PID
        if [[ "$1" =~ ^[0-9]+$ ]]; then
            apply_affinity "$1"
        else
            log_error "Unknown option: $1"
            echo "Use --help for usage"
            exit 1
        fi
        ;;
esac
