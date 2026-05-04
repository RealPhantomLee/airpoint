#!/bin/bash
# Airpoint — Quick Run Script (after installation)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"

echo "╔══════════════════════════════════════════╗"
echo "║  Airpoint — Touchless Cursor Control     ║"
echo "╚══════════════════════════════════════════╝"
echo

# Check if venv exists
if [ ! -d "$PROJECT_DIR/venv" ]; then
    echo "No virtual environment found."
    echo "Run the installer first:"
    echo "  ./scripts/install/linux.sh     (Linux)"
    echo "  ./scripts/install/macos.sh     (macOS)"
    echo
    exit 1
fi

# Activate and run
source "$PROJECT_DIR/venv/bin/activate"

echo "Starting Airpoint..."
echo
exec python "$PROJECT_DIR/app/main.py"
