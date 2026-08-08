#!/bin/bash
cd "$(dirname "$0")/.." || exit 1

export PATH="$HOME/.opencode/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
export NO_COLOR=1

if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

mkdir -p copilot

# Read task description into prompt variable
TASK_CONTENT=$(cat copilot/pending_task.md 2>/dev/null || echo "Run build and check code integrity.")

echo "🚀 Running OpenCode with latest pending task..."

# 'run' subcommand ensures opencode treats $TASK_CONTENT as the prompt
/Users/erikvilla/.opencode/bin/opencode run "$TASK_CONTENT" < /dev/null > build_output.tmp 2>&1

CHANGED_FILES=$(git status --porcelain)

cat << EOF > copilot/build_result.md
# 🤖 OpenCode Execution Report
**Timestamp:** $(date)

### 📁 Modified Files:
\`\`\`text
$CHANGED_FILES
\`\`\`

### 📜 Execution Logs:
\`\`\`text
$(cat build_output.tmp)
\`\`\`
EOF

rm -f build_output.tmp
echo "✅ Build complete! Report updated in build_result.md"