#!/usr/bin/env bash
# CookieRun Classic Bot - Installation (macOS / Linux)
# Pretty terminal via ui_console + install.py
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC_DIR="$SCRIPT_DIR/src"

# UTF-8
export PYTHONIOENCODING=utf-8
export LANG=en_US.UTF-8 2>/dev/null || true

if [ ! -d "$SRC_DIR" ]; then
  echo "[ERROR] src/ directory not found at $SRC_DIR"
  exit 1
fi
cd "$SRC_DIR"

# Find python
PYTHON="python3"
if ! command -v python3 >/dev/null 2>&1; then
  if command -v python >/dev/null 2>&1; then
    PYTHON="python"
  else
    echo "========================================================"
    echo "  [ERROR] Python 3.10+ not found in PATH"
    echo "  Install: https://www.python.org/downloads/  or  brew install python"
    echo "========================================================"
    exit 1
  fi
fi

echo "Using: $($PYTHON --version 2>&1) at $(command -v $PYTHON)"

if [ -f "install.py" ]; then
  $PYTHON install.py
  EXIT_CODE=$?
else
  echo "========================================================"
  echo "  CookieRun Classic Bot - Installing Dependencies..."
  echo "========================================================"
  $PYTHON -m pip install --upgrade pip
  $PYTHON -m pip install -r requirements.txt
  EXIT_CODE=$?
fi

if [ $EXIT_CODE -eq 0 ]; then
  echo ""
  echo "========================================================"
  echo "  [SUCCESS] Installation completed successfully!"
  echo "  Run: $PYTHON run_web.py  or  ./START_BOT.sh"
  echo "========================================================"
else
  echo ""
  echo "========================================================"
  echo "  [ERROR] Installation failed."
  echo "  Please ensure Python 3.10+ is installed and try again."
  echo "========================================================"
  exit $EXIT_CODE
fi
