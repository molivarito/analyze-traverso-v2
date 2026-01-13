#!/bin/bash
# Quick start script for Traverso Analyzer
# This script helps with initial setup

set -e  # Exit on error

echo "╔══════════════════════════════════════════════════════════╗"
echo "║     Traverso Analyzer - Quick Start Script              ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "✅ Python $PYTHON_VERSION found"

# Check if we're in a virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo ""
    echo "⚠️  You are not in a virtual environment."
    echo "   It's recommended to use a virtual environment."
    echo ""
    read -p "Create a virtual environment now? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Creating virtual environment..."
        python3 -m venv venv
        echo "Activating virtual environment..."
        source venv/bin/activate
        echo "✅ Virtual environment activated"
    fi
fi

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Run health check
echo ""
echo "Running health check..."
python3 check_health.py

# Check result
if [ $? -eq 0 ]; then
    echo ""
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║              Setup Complete!                             ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo ""
    echo "You can now run the main application:"
    echo "  python unified_flute_gui_qt.py"
    echo ""
    echo "Or use make commands:"
    echo "  make run              # Run main GUI"
    echo "  make run-experimenter # Run experimenter"
    echo "  make test             # Run tests"
    echo ""
else
    echo ""
    echo "⚠️  Setup completed with warnings. See messages above."
    echo "   You may need to install OpenWind manually."
    echo "   See INSTALL.md for details."
fi
