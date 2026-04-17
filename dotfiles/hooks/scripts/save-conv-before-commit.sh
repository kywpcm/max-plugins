#!/bin/bash
# Pre-commit hook: Ensure save-conversation is run before git commit
# Blocks git commit if no recent conversation log exists or if it's not staged.

set -euo pipefail

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""')

# Only intercept commands that contain git commit (including chained: git add ... && git commit ...)
if ! echo "$COMMAND" | grep -qE '(^|\&\&|;|\|)\s*git\s+commit(\s|$)'; then
  exit 0
fi

PROJECT_DIR=$(echo "$INPUT" | jq -r '.cwd // ""')
if [ -z "$PROJECT_DIR" ]; then
  PROJECT_DIR=$(pwd)
fi

# Allow the command itself to override PROJECT_DIR — handles the case where the
# Claude Code session cwd is not a git repo but the command runs inside one via
# `cd <path> && git commit` or `git -C <path> commit`. Only scan the portion of
# the command *before* the first `git commit` occurrence, so free text in the
# commit message (e.g. words like "cd" or "-C") never leaks into the parse.
PREFIX="${COMMAND%%git commit*}"
CMD_DIR=""
if printf '%s' "$PREFIX" | grep -qE 'git[[:space:]]+-C[[:space:]]+'; then
  CMD_DIR=$(printf '%s' "$PREFIX" | sed -nE 's/.*git[[:space:]]+-C[[:space:]]+("([^"]+)"|'"'"'([^'"'"']+)'"'"'|([^[:space:]]+)).*/\2\3\4/p' | head -1)
elif printf '%s' "$PREFIX" | grep -qE '(^|[&;(])[[:space:]]*cd[[:space:]]+'; then
  CMD_DIR=$(printf '%s' "$PREFIX" | sed -nE 's/.*(^|[&;(])[[:space:]]*cd[[:space:]]+("([^"]+)"|'"'"'([^'"'"']+)'"'"'|([^[:space:]&;|()]+)).*/\3\4\5/p' | head -1)
fi
if [ -n "$CMD_DIR" ]; then
  # Resolve ~ and relative paths against the session cwd
  case "$CMD_DIR" in
    '~'|'~/'*) CMD_DIR="${HOME}${CMD_DIR#\~}" ;;
    /*) ;;
    *) CMD_DIR="$PROJECT_DIR/$CMD_DIR" ;;
  esac
  if [ -d "$CMD_DIR" ]; then
    PROJECT_DIR="$CMD_DIR"
  fi
fi

# Resolve git repo root — conv-logs always lives at the project root
PROJECT_ROOT=$(git -C "$PROJECT_DIR" rev-parse --show-toplevel 2>/dev/null || echo "$PROJECT_DIR")

LOGDIR="$PROJECT_ROOT/conv-logs"

# Skip hook entirely when conv-logs/ is gitignored — user opted out of log-before-commit enforcement
if git -C "$PROJECT_ROOT" check-ignore -q conv-logs 2>/dev/null; then
  exit 0
fi

# Check if conv-logs directory exists and has conv logs
if [ ! -d "$LOGDIR" ]; then
  cat >&2 <<'EOF'
{
  "decision": "deny",
  "reason": "git commit intercepted: no conversation log found",
  "systemMessage": "HOOK INSTRUCTION: Before running git commit, you MUST do the following steps in order:\n1. Run the save-conversation skill (invoke Skill tool with skill: 'save-conversation')\n2. Then retry the original git commit command.\n\nDo NOT skip these steps. Do NOT ask the user for confirmation - just do it."
}
EOF
  exit 2
fi

# Find the most recent conv-*.md file (search recursively in subdirectories)
LATEST_LOG=$(find "$LOGDIR" -name 'conv-*.md' -type f -print0 2>/dev/null | xargs -0 ls -t 2>/dev/null | head -1)

if [ -z "$LATEST_LOG" ]; then
  cat >&2 <<'EOF'
{
  "decision": "deny",
  "reason": "git commit intercepted: no conversation log found",
  "systemMessage": "HOOK INSTRUCTION: Before running git commit, you MUST do the following steps in order:\n1. Run the save-conversation skill (invoke Skill tool with skill: 'save-conversation')\n2. Then retry the original git commit command.\n\nDo NOT skip these steps. Do NOT ask the user for confirmation - just do it."
}
EOF
  exit 2
fi

# Check if the latest log was created recently (within last 3 minutes)
if [[ "$OSTYPE" == "darwin"* ]]; then
  FILE_TIME=$(stat -f %m "$LATEST_LOG")
else
  FILE_TIME=$(stat -c %Y "$LATEST_LOG")
fi
CURRENT_TIME=$(date +%s)
AGE=$(( CURRENT_TIME - FILE_TIME ))

if [ "$AGE" -gt 180 ]; then
  cat >&2 <<'EOF'
{
  "decision": "deny",
  "reason": "git commit intercepted: conversation log is older than 1 minute",
  "systemMessage": "HOOK INSTRUCTION: The latest conversation log is stale. Before running git commit, you MUST do the following steps in order:\n1. Run the save-conversation skill (invoke Skill tool with skill: 'save-conversation')\n2. Then retry the original git commit command.\n\nDo NOT skip these steps. Do NOT ask the user for confirmation - just do it."
}
EOF
  exit 2
fi

# Check if the latest log is staged or already committed
RELATIVE_LOG=$(python3 -c "import os,sys; print(os.path.relpath(sys.argv[1], sys.argv[2]))" "$LATEST_LOG" "$PROJECT_ROOT")

cd "$PROJECT_ROOT"
if ! git diff --cached --name-only | grep -qF "$RELATIVE_LOG"; then
  if ! git ls-files --error-unmatch "$RELATIVE_LOG" >/dev/null 2>&1; then
    cat >&2 <<EOF
{
  "decision": "deny",
  "reason": "git commit intercepted: conversation log not staged",
  "systemMessage": "HOOK INSTRUCTION: Conversation log exists but is not staged. Run: git add \"$RELATIVE_LOG\" and then retry the git commit."
}
EOF
    exit 2
  fi
fi

# All checks passed
exit 0
