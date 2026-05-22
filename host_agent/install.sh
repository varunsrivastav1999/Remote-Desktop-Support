#!/bin/bash
# ─────────────────────────────────────────────────────────────
# Remote Desktop Host Agent — Quick Install Script
#
# Usage:
#   curl -sSL http://YOUR_SERVER:8000/install.sh | bash
#   - OR -
#   bash install.sh
#
# This script:
#   1. Creates a directory for the agent
#   2. Downloads agent files (or copies from local)
#   3. Installs Python dependencies
#   4. Starts the agent
# ─────────────────────────────────────────────────────────────

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

AGENT_DIR="$HOME/.remote-desktop-agent"
SERVER_URL="${1:-http://localhost:8000}"

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║     Remote Desktop Host Agent — Installer                    ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# ─── Check Python ────────────────────────────────────────────
echo -e "${YELLOW}[1/4]${NC} Checking Python..."
if command -v python3 &>/dev/null; then
    PYTHON=python3
    PIP=pip3
elif command -v python &>/dev/null; then
    PYTHON=python
    PIP=pip
else
    echo -e "${RED}✗ Python 3.8+ is required. Please install Python first.${NC}"
    echo "  Ubuntu/Debian: sudo apt install python3 python3-pip python3-venv"
    echo "  macOS: brew install python3"
    echo "  Windows: https://www.python.org/downloads/"
    exit 1
fi

PY_VERSION=$($PYTHON --version 2>&1 | awk '{print $2}')
echo -e "${GREEN}  ✓ Found $PYTHON ($PY_VERSION)${NC}"

# ─── Create agent directory ─────────────────────────────────
echo -e "${YELLOW}[2/4]${NC} Setting up agent directory..."
mkdir -p "$AGENT_DIR"

# ─── Copy or download agent files ───────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENT_FILES=(agent.py signaling_client.py screen_capture.py input_handler.py file_transfer.py requirements.txt)

if [ -f "$SCRIPT_DIR/agent.py" ]; then
    echo "  → Copying agent files from local directory..."
    for f in "${AGENT_FILES[@]}"; do
        if [ -f "$SCRIPT_DIR/$f" ]; then
            cp "$SCRIPT_DIR/$f" "$AGENT_DIR/"
            echo "    ✓ $f"
        fi
    done
else
    echo "  → Agent files not found locally."
    echo "  → Please copy the following files to $AGENT_DIR:"
    for f in "${AGENT_FILES[@]}"; do
        echo "    - $f"
    done
    echo ""
    echo "  Or run this script from the host_agent/ directory."
    exit 1
fi

# ─── Install dependencies ───────────────────────────────────
echo -e "${YELLOW}[3/4]${NC} Installing Python dependencies..."

# Create virtual environment
if [ ! -d "$AGENT_DIR/venv" ]; then
    $PYTHON -m venv "$AGENT_DIR/venv" 2>/dev/null || {
        echo -e "${YELLOW}  ⚠ venv creation failed, installing globally...${NC}"
        $PIP install -r "$AGENT_DIR/requirements.txt"
    }
fi

if [ -d "$AGENT_DIR/venv" ]; then
    source "$AGENT_DIR/venv/bin/activate" 2>/dev/null || source "$AGENT_DIR/venv/Scripts/activate" 2>/dev/null
    pip install -r "$AGENT_DIR/requirements.txt"
fi

echo -e "${GREEN}  ✓ Dependencies installed${NC}"

# ─── Platform-specific setup ────────────────────────────────
OS=$(uname -s)
if [ "$OS" = "Linux" ]; then
    echo ""
    echo -e "${YELLOW}  Linux detected — checking X11 dependencies...${NC}"
    
    # Check for required system packages
    MISSING=""
    for pkg in python3-xlib xdotool xclip; do
        if ! dpkg -s "$pkg" &>/dev/null 2>&1; then
            MISSING="$MISSING $pkg"
        fi
    done
    
    if [ -n "$MISSING" ]; then
        echo -e "${YELLOW}  Installing missing system packages:$MISSING${NC}"
        sudo apt-get update -qq && sudo apt-get install -y -qq $MISSING 2>/dev/null || {
            echo -e "${YELLOW}  ⚠ Could not install:$MISSING (you may need to install manually)${NC}"
        }
    fi
fi

# ─── Create startup script ──────────────────────────────────
cat > "$AGENT_DIR/start.sh" << EOF
#!/bin/bash
cd "$AGENT_DIR"
if [ -d "venv" ]; then
    source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null
fi
python agent.py --server $SERVER_URL "\$@"
EOF
chmod +x "$AGENT_DIR/start.sh"

# ─── Done ────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ✓ Installation Complete!                                    ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${CYAN}To start the agent:${NC}"
echo -e "    ${GREEN}$AGENT_DIR/start.sh${NC}"
echo ""
echo -e "  ${CYAN}Or with options:${NC}"
echo -e "    ${GREEN}$AGENT_DIR/start.sh --fps 60 --quality high${NC}"
echo ""
echo -e "  ${CYAN}Server URL:${NC} $SERVER_URL"
echo ""

# ─── Ask to start now ───────────────────────────────────────
read -p "Start the agent now? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    exec "$AGENT_DIR/start.sh"
fi
