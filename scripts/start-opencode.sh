#!/bin/bash
set -a
source /Users/admin/projects/jarvis/.env
set +a

PROJECT_DIR="/Users/admin/projects/jarvis"
export XDG_DATA_HOME="$PROJECT_DIR/vault/raw"
export XDG_STATE_HOME="$PROJECT_DIR/vault/index/opencode-state"

mkdir -p "$XDG_DATA_HOME/opencode"
mkdir -p "$XDG_STATE_HOME"
mkdir -p "$PROJECT_DIR/vault/index"
mkdir -p "$PROJECT_DIR/vault/raw/bookmarks"
mkdir -p "$PROJECT_DIR/vault/raw/url-saves"
mkdir -p "$PROJECT_DIR/vault/raw/attachments"

cd "$PROJECT_DIR"
LOG_DIR="$PROJECT_DIR/vault/index/opencode-logs"
mkdir -p "$LOG_DIR"
LOG_LEVEL="${OPENCODE_LOG_LEVEL:-INFO}"
exec opencode serve --port 4096 \
  --print-logs --log-level "$LOG_LEVEL" \
  2>&1 | tee -a "$LOG_DIR/server-$(date +%Y%m%d).log"
