#!/bin/bash
set -a
source /Users/admin/projects/jarvis/.env
set +a
cd /Users/admin/projects
LOG_DIR="$HOME/.opencode/logs"
mkdir -p "$LOG_DIR"
LOG_LEVEL="${OPENCODE_LOG_LEVEL:-INFO}"
exec opencode serve --port 4096 \
  --print-logs --log-level "$LOG_LEVEL" \
  2>&1 | tee -a "$LOG_DIR/server-$(date +%Y%m%d).log"
