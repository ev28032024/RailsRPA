#!/bin/bash
# Shell script to run AdsPower Discord Automation on Linux/Mac

echo "============================================================"
echo "  AdsPower Discord Automation RPA"
echo "============================================================"
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed or not in PATH"
    echo "Please install Python 3.8 or higher"
    exit 1
fi

# Check if config exists
if [ ! -f "config.yaml" ]; then
    echo "ERROR: config.yaml not found"
    echo "Please create configuration file from config.example.yaml"
    echo ""
    echo "Run: cp config.example.yaml config.yaml"
    echo "Then edit config.yaml with your settings"
    exit 1
fi

# Run the automation
python3 main.py

