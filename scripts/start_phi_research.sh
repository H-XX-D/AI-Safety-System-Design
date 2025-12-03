#!/bin/bash
# Quick start script for Phi research

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║           PHI RESEARCH RUNNER - QUICK START                  ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check if Phi server is running
echo -e "${YELLOW}Checking Phi server...${NC}"
if curl -s http://localhost:8080/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Phi server is running${NC}"
else
    echo -e "${YELLOW}⚠ Phi server not detected at localhost:8080${NC}"
    echo "  Start it with: ./llama-server -m phi-3.5-mini.gguf"
    echo ""
fi

# Check if PaperQA is running (optional)
echo -e "${YELLOW}Checking PaperQA server...${NC}"
if curl -s http://localhost:5000/api/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ PaperQA server is running${NC}"
else
    echo -e "${YELLOW}⚠ PaperQA server not detected (will use mock papers)${NC}"
fi

echo ""
echo -e "${BLUE}Starting research runner...${NC}"
echo ""

# Run the research runner
cd "$(dirname "$0")/.."
python scripts/phi_research_runner.py "$@"

