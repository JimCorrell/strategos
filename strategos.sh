#!/bin/bash
# STRATEGOS Shell Launcher
# Quick launcher script for STRATEGOS simulation engine

set -e  # Exit on error

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Ensure we're using the correct Python version with pyenv
if command -v pyenv &> /dev/null; then
    export PYENV_VERSION=$(cat .python-version 2>/dev/null || echo "3.12.10")
    echo "🐍 Using Python $(python --version 2>&1)"
fi

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "⚠️  Virtual environment not found. Creating..."
    python -m venv .venv
    echo "✓ Virtual environment created"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip if needed
if [ ! -f ".venv/.pip_upgraded" ]; then
    echo "📦 Upgrading pip..."
    pip install -q --upgrade pip
    touch .venv/.pip_upgraded
fi

# Check if dependencies are installed
if [ ! -f ".venv/.deps_installed" ] || ! python -c "import fastapi" 2>/dev/null; then
    echo "📦 Installing dependencies..."
    pip install -q -r requirements.txt
    touch .venv/.deps_installed
    echo "✓ Dependencies installed"
fi

# Run the Python launcher
echo "🚀 Starting STRATEGOS..."
python strategos.py "$@"
