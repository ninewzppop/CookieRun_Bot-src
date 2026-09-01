#!/usr/bin/env bash
# CookieRun Classic Bot - Web Dashboard Launcher (macOS / Linux)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC_DIR="$SCRIPT_DIR/src"
export PYTHONIOENCODING=utf-8
cd "$SRC_DIR"

PYTHON="python3"
if ! command -v python3 >/dev/null 2>&1; then
  if command -v python >/dev/null 2>&1; then PYTHON="python"; else echo "[ERROR] python not found"; exit 1; fi
fi

$PYTHON run_web.py
EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
  echo ""
  echo "[ERROR] Cannot run Python or required packages are missing!"
  echo "Please run: ./INSTALL.sh  or  pip install -r requirements.txt"
  echo "  Tip: pip install -r requirements.txt"
  exit $EXIT_CODE
fi
