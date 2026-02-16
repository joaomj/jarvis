#!/bin/bash
set -a
source /Users/admin/projects/jarvis/.env
set +a
cd /Users/admin/projects/jarvis
exec /opt/homebrew/bin/pdm run python -m jarvis
