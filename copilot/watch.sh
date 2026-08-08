cat << 'EOF' > copilot/watch.sh
#!/bin/zsh
echo "� Watching copilot/pending_task.md for changes..."
LAST_MOD=$(stat -f "%m" copilot/pending_task.md 2>/dev/null)

while true; do
  CURRENT_MOD=$(stat -f "%m" copilot/pending_task.md 2>/dev/null)
  if [[ "$CURRENT_MOD" != "$LAST_MOD" && -n "$LAST_MOD" ]]; then
    echo "\n⚡ New task detected in pending_task.md!"
    echo "=========================================="
    
    # Run OpenCode build
    ./copilot/run_build.sh
    
    # Auto-push local commits to GitHub
    echo "� Pushing commits to GitHub..."
    git push origin main
    
    echo "=========================================="
    echo "� Watching for next task save..."
    LAST_MOD=$CURRENT_MOD
  fi
  sleep 1
done
EOF

chmod +x copilot/watch.sh