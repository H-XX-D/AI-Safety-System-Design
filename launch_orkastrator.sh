#!/bin/bash
#
# ORKASTRATOR System Launcher
# ============================
# Launches the AI Safety System with all components
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="/home/xx/AI-Safety-System-Design"
LOG_DIR="$PROJECT_DIR/logs"
VENV_DIR="$PROJECT_DIR/.venv"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Create logs directory
mkdir -p "$LOG_DIR"

echo -e "${CYAN}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║                                                           ║"
echo "║     ██████╗ ██████╗ ██╗  ██╗ █████╗                      ║"
echo "║    ██╔═══██╗██╔══██╗██║ ██╔╝██╔══██╗                     ║"
echo "║    ██║   ██║██████╔╝█████╔╝ ███████║                     ║"
echo "║    ██║   ██║██╔══██╗██╔═██╗ ██╔══██║                     ║"
echo "║    ╚██████╔╝██║  ██║██║  ██╗██║  ██║                     ║"
echo "║     ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝                     ║"
echo "║                                                           ║"
echo "║           AI Safety System - ORKASTRATOR                  ║"
echo "║                                                           ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Function to check if a service is running
check_service() {
    local name=$1
    local port=$2
    if nc -z localhost $port 2>/dev/null; then
        echo -e "${GREEN}✓${NC} $name is running on port $port"
        return 0
    else
        echo -e "${YELLOW}○${NC} $name not running on port $port"
        return 1
    fi
}

# Function to check nano status
check_nanos() {
    echo -e "\n${BLUE}Checking Nano Cluster...${NC}"
    local online=0
    local nodes=("gin@192.168.0.242" "orin@192.168.0.160" "tif@192.168.0.213" "tori@192.168.0.235" "page@192.168.0.168" "archi@192.168.0.232" "guard@192.168.0.146")
    
    for node in "${nodes[@]}"; do
        name=$(echo $node | cut -d@ -f1 | tr '[:lower:]' '[:upper:]')
        ip=$(echo $node | cut -d@ -f2)
        if timeout 2 nc -z $ip 11434 2>/dev/null; then
            echo -e "  ${GREEN}✓${NC} $name ($ip)"
            ((online++))
        else
            echo -e "  ${RED}✗${NC} $name ($ip)"
        fi
    done
    echo -e "${BLUE}Nanos online: $online/7${NC}"
}

# Activate virtual environment
activate_venv() {
    if [ -d "$VENV_DIR" ]; then
        source "$VENV_DIR/bin/activate"
        echo -e "${GREEN}✓${NC} Virtual environment activated"
    else
        echo -e "${YELLOW}!${NC} No virtual environment found at $VENV_DIR"
    fi
}

# Start the UI server
start_ui() {
    echo -e "\n${BLUE}Starting UI Server...${NC}"
    
    if check_service "UI Server" 5001; then
        echo -e "${YELLOW}  UI already running${NC}"
        return 0
    fi
    
    cd "$PROJECT_DIR"
    activate_venv
    
    # Start Flask UI in background
    nohup python "$PROJECT_DIR/ui/app.py" --host 0.0.0.0 --port 5001 > "$LOG_DIR/ui.log" 2>&1 &
    UI_PID=$!
    echo $UI_PID > "$PROJECT_DIR/ui.pid"
    
    # Wait for startup
    echo -n "  Starting"
    for i in {1..10}; do
        sleep 1
        echo -n "."
        if nc -z localhost 5001 2>/dev/null; then
            echo ""
            echo -e "${GREEN}✓${NC} UI Server started on http://localhost:5001"
            return 0
        fi
    done
    echo ""
    echo -e "${RED}✗${NC} UI Server failed to start. Check $LOG_DIR/ui.log"
    return 1
}

# Open browser
open_browser() {
    echo -e "\n${BLUE}Opening browser...${NC}"
    sleep 1
    
    if command -v xdg-open &> /dev/null; then
        xdg-open "http://localhost:5001" 2>/dev/null &
    elif command -v gnome-open &> /dev/null; then
        gnome-open "http://localhost:5001" 2>/dev/null &
    elif command -v firefox &> /dev/null; then
        firefox "http://localhost:5001" 2>/dev/null &
    elif command -v chromium-browser &> /dev/null; then
        chromium-browser "http://localhost:5001" 2>/dev/null &
    else
        echo -e "${YELLOW}!${NC} Could not open browser. Please navigate to http://localhost:5001"
    fi
}

# Stop all services
stop_services() {
    echo -e "\n${BLUE}Stopping services...${NC}"
    
    # Stop UI
    if [ -f "$PROJECT_DIR/ui.pid" ]; then
        UI_PID=$(cat "$PROJECT_DIR/ui.pid")
        if kill -0 $UI_PID 2>/dev/null; then
            kill $UI_PID
            echo -e "${GREEN}✓${NC} UI Server stopped"
        fi
        rm "$PROJECT_DIR/ui.pid"
    fi
    
    # Kill any remaining Flask processes for this project
    pkill -f "python.*ui/app.py" 2>/dev/null
    
    echo -e "${GREEN}✓${NC} All services stopped"
}

# Show status
show_status() {
    echo -e "\n${BLUE}=== System Status ===${NC}\n"
    
    # Local services
    echo -e "${CYAN}Local Services:${NC}"
    check_service "UI Server" 5001
    check_service "Ollama (ORKA)" 11434
    
    # Nano cluster
    check_nanos
    
    echo ""
}

# Main menu
show_menu() {
    echo -e "\n${CYAN}What would you like to do?${NC}"
    echo "  1) Start System (UI + open browser)"
    echo "  2) Show Status"
    echo "  3) Stop System"
    echo "  4) Restart System"
    echo "  5) View Logs"
    echo "  6) Exit"
    echo ""
    read -p "Select option [1-6]: " choice
    
    case $choice in
        1)
            start_ui
            open_browser
            show_menu
            ;;
        2)
            show_status
            show_menu
            ;;
        3)
            stop_services
            show_menu
            ;;
        4)
            stop_services
            sleep 2
            start_ui
            open_browser
            show_menu
            ;;
        5)
            echo -e "\n${BLUE}Recent UI logs:${NC}"
            tail -30 "$LOG_DIR/ui.log" 2>/dev/null || echo "No logs found"
            show_menu
            ;;
        6)
            echo -e "\n${GREEN}Goodbye!${NC}\n"
            exit 0
            ;;
        *)
            echo -e "${RED}Invalid option${NC}"
            show_menu
            ;;
    esac
}

# Handle command line arguments
case "${1:-}" in
    --start|-s)
        start_ui
        open_browser
        ;;
    --stop)
        stop_services
        ;;
    --status)
        show_status
        ;;
    --restart|-r)
        stop_services
        sleep 2
        start_ui
        open_browser
        ;;
    --help|-h)
        echo "Usage: $0 [OPTION]"
        echo ""
        echo "Options:"
        echo "  --start, -s    Start the system and open browser"
        echo "  --stop         Stop all services"
        echo "  --status       Show system status"
        echo "  --restart, -r  Restart the system"
        echo "  --help, -h     Show this help"
        echo ""
        echo "Without options, shows interactive menu."
        ;;
    *)
        show_status
        show_menu
        ;;
esac
