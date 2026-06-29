#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG="$SCRIPT_DIR/support-team-planner.log"

if pgrep -f "python3 support_planner.py" > /dev/null; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') EXIT: support-team-planner already running" >> "$LOG"
    exit 0
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') Start support-team-planner" >> "$LOG"
nohup /bin/bash "$SCRIPT_DIR/run.sh" >> "$LOG" 2>&1 &
