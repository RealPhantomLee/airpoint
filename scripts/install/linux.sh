#!/bin/bash
# Airpoint — Linux Installation Script
# Tested on: Arch Linux, Ubuntu, Debian, Fedora

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Airpoint — Linux Installer              ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo

# Detect package manager
if command -v pacman &>/dev/null; then
    PKG_MANAGER="pacman"
    PKG_CMD="sudo pacman -S --noconfirm"
elif command -v apt-get &>/dev/null; then
    PKG_MANAGER="apt"
    PKG_CMD="sudo apt-get install -y"
elif command -v dnf &>/dev/null; then
    PKG_MANAGER="dnf"
    PKG_CMD="sudo dnf install -y"
elif command -v yum &>/dev/null; then
    PKG_MANAGER="yum"
    PKG_CMD="sudo yum install -y"
else
    echo -e "${RED}Error: No supported package manager found.${NC}"
    echo "Install Python, pip, and your webcam drivers manually."
    exit 1
fi

echo -e "${YELLOW}Detected package manager: $PKG_MANAGER${NC}"
echo

# Install system dependencies
echo -e "${GREEN}[1/4] Installing system dependencies...${NC}"
case $PKG_MANAGER in
    pacman)
        sudo pacman -Sy --needed python python-pip git v4l-utils libgl mesa 2>/dev/null || true
        ;;
    apt)
        sudo apt-get update -qq
        $PKG_CMD python3 python3-pip python3-venv git v4l-utils libgl1-mesa-glx 2>/dev/null || true
        ;;
    dnf|yum)
        $PKG_CMD python3 python3-pip git v4l-utils mesa-libGL 2>/dev/null || true
        ;;
esac

# Check for Python
if ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
    echo -e "${RED}Python not found. Please install Python 3.10+.${NC}"
    exit 1
fi

PYTHON=$(command -v python3 2>/dev/null || command -v python)
echo -e "${GREEN}Python found: $($PYTHON --version)${NC}"

# Create virtual environment
echo -e "${GREEN}[2/4] Setting up virtual environment...${NC}"
cd "$PROJECT_DIR"
$PYTHON -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip --quiet

# Install Python dependencies
echo -e "${GREEN}[3/4] Installing Python dependencies...${NC}"
pip install -r requirements.txt --quiet

# Verify camera access
echo -e "${GREEN}[4/4] Checking webcam...${NC}"
if [ -e "/dev/video0" ]; then
    echo -e "${GREEN}Webcam detected: /dev/video0${NC}"
else
    echo -e "${YELLOW}No webcam detected at /dev/video0${NC}"
    echo "You may need to set a different device_index in app/config/settings.json"
fi

echo
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Installation Complete!                  ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo
echo "To start Airpoint:"
echo "  cd $(basename $PROJECT_DIR)"
echo "  source venv/bin/activate"
echo "  python app/main.py"
echo
echo "Or use the quick start:"
echo "  ./run.sh"
