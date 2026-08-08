#!/bin/zsh
echo "� Watching copilot/pending_task.md for changes..."
LAST_MOD=$(stat -f "%m" copilot/pending_task.md 2>/dev/null)

while true; do
  CURRENT_MOD=$(stat -f "%m" copilot/pending_task.md 2>/dev/null)
  if [[ "$CURRENT_MOD" != "$LAST_MOD" ]]; then
    echo "\n⚡ New task detected! Launching OpenCode..."
    ./copilot/run_build.sh
    LAST_MOD=$(stat -f "%m" copilot/pending_task.md 2>/dev/null)
  fi
  sleep 1
done