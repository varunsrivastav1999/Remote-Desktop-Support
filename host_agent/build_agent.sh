#!/usr/bin/env bash
# build_agent.sh
# Builds the host agent into a single standalone executable using PyInstaller.
# This makes it "zero configuration" and "ready to run" without needing python/pip installed.

set -e

# Change to the script's directory
cd "$(dirname "$0")"

echo "Installing build dependencies..."
pip install -r requirements.txt
pip install pyinstaller

echo "Building standalone executable..."
# Use --onefile to create a single binary
# Use --clean to remove cached PyInstaller files
pyinstaller --noconfirm --clean --onefile --name "RemoteSupportAgent" agent.py

echo "Build complete!"
echo "The executable is located at: dist/RemoteSupportAgent"
