---
name: agent-team-starter
description: >
  Use this skill to spawn a multi-agent workspace with Codex and Gemini running
  alongside Claude in tmux panes. Trigger on "agent team", "agent team 시작",
  "agent team 준비", "agent team 시작해", "agent team 준비해", "에이전트 팀 시작",
  "에이전트 팀 준비", "agent team", "에이전트 팀", "codex랑 gemini 같이",
  "start agent team", "팀 시작", "멀티 에이전트 시작", "codex gemini 같이 띄워",
  "에이전트 팀 만들어", "spawn agents", "launch agents", "에이전트 pane 열어",
  "agent pane", "start multi-agent", "codex gemini pane".
  Also trigger when the user wants Codex and Gemini running side-by-side in tmux
  panes for parallel work, or asks to set up a multi-agent development environment.
  Do NOT trigger when the user just wants to delegate a single task to codex or gemini
  — use codex-delegate or gemini-delegate for that. This skill is specifically for
  spawning persistent agent panes in tmux.
version: 0.1.0
---

# Agent Team

Spawn Codex (`--full-auto`) and Gemini (`--yolo`) in tmux panes alongside the current Claude session. Skips creation if they're already running in the same tmux session.

## Prerequisites

- tmux must be running and the current shell must be inside it (`$TMUX` set)
- `codex` and `gemini` CLI binaries must be available
- (Optional, cosmetic only) tmux configured with `set -g pane-border-status top` and `set -g pane-border-format "#{pane_title}"` for a brief visual label above each pane. Detection works without it — we mark panes with the `@agent_role` user option, which is independent of pane border display.

## Workflow

### Step 1: Verify tmux environment

```bash
if [ -z "${TMUX:-}" ]; then
  echo "ERROR: Not inside a tmux session. Start tmux first (e.g., 'tmux new -s work')."
  exit 1
fi
CURRENT_PANE="${TMUX_PANE}"                          # caller's pane id, e.g. %12
CURRENT_SESSION=$(tmux display-message -p '#S')     # caller's session name
```

If tmux is not available or we're not inside one, inform the user and stop.

### Step 2: Check for existing agent panes

The skill marks each agent pane with the tmux user option `@agent_role` on creation. We use this rather than the visible pane title because Codex/Gemini TUIs eventually overwrite the title with their own status text — `@agent_role` is private to us and they cannot touch it.

```bash
# List every pane in the current session as "<pane_id>|<role>"
# Panes without @agent_role just produce "<pane_id>|" (empty 2nd field).
tmux list-panes -s -t "$CURRENT_SESSION" -F '#{pane_id}|#{@agent_role}'
```

Parse each line:
- `CODEX_PANE=<id>` if any line is `<id>|codex`
- `GEMINI_PANE=<id>` if any line is `<id>|gemini`

If both are already present, inform the user and stop:
> "Codex와 Gemini가 이미 이 tmux 세션에서 실행 중입니다."

### Step 3: Check CLI availability

Only check for CLIs that need to be launched:

```bash
command -v codex  &>/dev/null && echo "codex available"
command -v gemini &>/dev/null && echo "gemini available"
```

If a needed CLI is missing, warn the user but continue with the other agent.

### Step 4: Create Codex pane (split right)

`tmux split-window -P -F '#{pane_id}'` prints the new pane id to stdout — capture it for follow-up commands.

```bash
CODEX_PANE=$(tmux split-window -h -t "$CURRENT_PANE" -P -F '#{pane_id}')

# Shell readiness check via tmux IPC round-trip (no hard sleep per project convention).
# capture-pane naturally paces ~10–50ms — enough for shell init without an arbitrary sleep.
tmux capture-pane -p -t "$CODEX_PANE" >/dev/null 2>&1 || true

tmux send-keys -t "$CODEX_PANE" "codex --full-auto" Enter
tmux select-pane -t "$CODEX_PANE" -T "Codex"            # visual label (TUI may overwrite later)
tmux set-option -p -t "$CODEX_PANE" @agent_role 'codex' # programmatic marker — TUI cannot touch user options
```

### Step 5: Create Gemini pane (split down from Codex pane)

Split down from the Codex pane so Gemini appears below Codex, not below Claude.

```bash
GEMINI_PANE=$(tmux split-window -v -t "$CODEX_PANE" -P -F '#{pane_id}')

tmux capture-pane -p -t "$GEMINI_PANE" >/dev/null 2>&1 || true

# Default model — change here if you want a different Gemini version.
tmux send-keys -t "$GEMINI_PANE" "gemini --yolo --model gemini-3.1-pro-preview" Enter
tmux select-pane -t "$GEMINI_PANE" -T "Gemini"            # visual label (TUI may overwrite later)
tmux set-option -p -t "$GEMINI_PANE" @agent_role 'gemini' # programmatic marker — TUI cannot touch user options
```

If only Gemini needs to be created (Codex already running), split down from the existing Codex pane found in Step 2. If Codex is not present either (e.g., codex CLI missing), split right from the current Claude pane:

```bash
GEMINI_PANE=$(tmux split-window -h -t "$CURRENT_PANE" -P -F '#{pane_id}')
```

### Step 6: Return focus to Claude pane

```bash
tmux select-pane -t "$CURRENT_PANE"
```

### Step 7: Notify and report

tmux has no native OS-notification API, so use macOS notifications via `osascript`. Optionally also flash a tmux status message for in-terminal feedback.

```bash
osascript -e 'display notification "Codex and Gemini are running" with title "Agent Team Ready"'
tmux display-message "Agent Team Ready"
```

Display a summary to the user:

```
Agent Team 구성 완료:
┌─────────────────┬─────────────────┐
│                 │ Codex           │
│  Claude (현재)   │ (--full-auto)   │
│                 ├─────────────────┤
│                 │ Gemini          │
│                 │ (--yolo)        │
└─────────────────┴─────────────────┘
```

## Edge Cases

- **Only one agent missing**: If codex is already running but gemini is not (or vice versa), only create the missing pane. When creating just the gemini pane without a codex pane to split from, split right from the current Claude pane instead.
- **Neither CLI available**: Inform the user which CLIs are missing and how to install them.
- **tmux not running**: Tell the user to start tmux first (e.g., `tmux new -s work`). Do not fall back to plain shell — the agent panes need a multiplexer.
- **Already in a complex layout**: The skill always splits from the current pane / Codex pane. If the layout is already complex, the new panes will be added relative to whatever is currently focused.
- **Pane titles not visually displayed**: If you don't see "Codex" / "Gemini" labels above each pane, your tmux config likely lacks `set -g pane-border-status top` and `set -g pane-border-format "#{pane_title}"`. This is purely cosmetic — pane detection uses the `@agent_role` user option which is independent of the border display. Note that Codex and Gemini TUIs eventually overwrite the visible title with their own status text, so the label is mainly useful in the first few seconds after creation; long-term identification always goes through `@agent_role`.
