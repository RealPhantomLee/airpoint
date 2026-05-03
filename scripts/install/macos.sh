#!/bin/bash
# Airpoint — macOS Installation Script

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Airpoint — macOS Installer              ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo

# Check for Homebrew
if ! command -v brew &>/dev/null; then
    echo -e "${YELLOW}Homebrew not found. Installing...${NC}"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# Install system dependencies
echo -e "${GREEN}[1/3] Installing dependencies via Homebrew...${NC}"
brew install python git
brew install ffmpeg  # for camera support (optional)

# Check Python version
PYTHON=$(command -v python3)
PYTHON_VERSION=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]; then
    echo -e "${RED}Python 3.10+ required. Found $PYTHON_VERSION${NC}"
    exit 1
fi

echo -e "${GREEN}Python found: $($PYTHON --version)${NC}"

# Create virtual environment
echo -e "${GREEN}[2/3] Setting up virtual environment...${NC}"
cd "$PROJECT_DIR"
$PYTHON -m venv venv
source venv/bin/activate
pip install --upgrade pip --quiet

# Install Python dependencies
echo -e "${GREEN}[3/3] Installing Python packages...${NC}"
pip install -r requirements.txt --quiet

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
echo "Note: macOS may prompt for camera access on first run. Allow it."
