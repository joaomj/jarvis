#!/bin/bash
set -a
source /Users/admin/projects/jarvis/.env
set +a
exec /Users/admin/.opencode/bin/opencode serve --port 4096
