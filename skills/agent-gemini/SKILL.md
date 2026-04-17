---
name: agent-gemini
description: >
  Use this skill to send a task to Gemini running in a tmux pane and get the result back
  as a file. Trigger on "agent gemini", "agent gemini에게", "agent gemini한테",
  "agent gemini로", "agent gemini에게 해줘", "agent gemini한테 시켜",
  "agent gemini로 보내", "agent gemini에게 물어봐".
  Only trigger when the user explicitly says "agent gemini" — the "agent" prefix is
  required to distinguish from gemini-delegate. Do NOT trigger on bare "gemini" mentions
  without the "agent" prefix. This skill communicates with a persistent Gemini pane
  in tmux (started by agent-team-starter) and collects the result via a file.
  Do NOT trigger for gemini-delegate (which launches a new gemini process in the background).
version: 0.1.0
---

# agent-gemini

Send a prompt to the Gemini pane in tmux and collect the result as a markdown file.

This skill works with a Gemini instance already running in a tmux pane (typically started by `agent-team-starter`). It sends the user's task as a prompt, asks Gemini to write the result to a file, then watches for that file and presents the result.

## Workflow

### Step 1: Find the Gemini pane

The Gemini pane is identified by the tmux user option `@agent_role` (set to `gemini` by `agent-team-starter`). We use this rather than the pane title because Gemini's TUI eventually overwrites the title with its own status text — `@agent_role` is private to us and stays put.

```bash
SESSION=$(tmux display-message -p '#S')
tmux list-panes -s -t "$SESSION" -F '#{pane_id}|#{@agent_role}' | awk -F'|' '$2 == "gemini" {print $1}'
```

Take the `<pane_id>` printed (e.g., `%17`). If nothing is printed, tell the user:
> "Gemini pane을 찾을 수 없습니다. `agent-team-starter` 스킬로 먼저 Gemini pane을 시작하세요."

Save the pane id as `GEMINI_PANE`.

### Step 2: Prepare the result file path

```bash
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
RESULT_DIR="$(pwd)/agent-team"
RESULT_FILE="$RESULT_DIR/gemini-result-${TIMESTAMP}.md"
mkdir -p "$RESULT_DIR"
```

### Step 3: Compose and send the prompt

Build the prompt to send to Gemini. The prompt wraps the user's task with instructions to write the result to the specific file path.

```
[USER'S TASK HERE]

When you are done, write your complete response (including any code, explanation, or analysis) to this file:
${RESULT_FILE}

Write the file using the Write tool or by running: cat > "${RESULT_FILE}" << 'RESULT_EOF'
[your response here]
RESULT_EOF
```

Send the prompt text via `tmux send-keys -l` (literal — no key interpretation), then a separate `Enter` keypress to submit. Gemini's composer needs an explicit Enter — sending text alone leaves the cursor on the line.

```bash
tmux send-keys -t "$GEMINI_PANE" -l "<prompt>"
tmux send-keys -t "$GEMINI_PANE" Enter
```

For prompts containing many special characters (quotes, backticks, `$`) or very long content, prefer the buffer approach — it bypasses shell quoting entirely:

```bash
PROMPT_FILE=$(mktemp /tmp/gemini-prompt-XXXXXX.txt)
# Write prompt content to PROMPT_FILE
tmux load-buffer "$PROMPT_FILE"
tmux paste-buffer -t "$GEMINI_PANE"
tmux send-keys -t "$GEMINI_PANE" Enter
rm "$PROMPT_FILE"
```

### Step 4: Launch file watcher in background

Start a background process that polls for the result file. Use Bash with `run_in_background: true`:

```bash
# Poll every 3 seconds for up to 30 minutes (600 checks)
RESULT_FILE="<result_file_path>"
for i in $(seq 1 600); do
  if [ -f "$RESULT_FILE" ] && [ -s "$RESULT_FILE" ]; then
    echo "RESULT_READY: $RESULT_FILE"
    cat "$RESULT_FILE"
    exit 0
  fi
  sleep 3
done
echo "TIMEOUT: Gemini did not write result within 30 minutes"
exit 1
```

### Step 5: Notify the user and wait

Tell the user the prompt has been sent:
> "Gemini pane에 프롬프트를 전송했습니다. 결과 파일을 기다리고 있습니다: `agent-team/gemini-result-{timestamp}.md`"

The background process will notify when the file appears. When the task notification arrives, read the result file and present it to the user.

### Step 6: Present the result

When the background watcher completes:

1. Read the result file
2. Present the content to the user with a header indicating the source:
   > **Gemini Result** (`agent-team/gemini-result-{timestamp}.md`)
3. If the watcher timed out, inform the user and suggest checking the Gemini pane manually:
   > "Gemini가 30분 내에 결과를 작성하지 않았습니다. Gemini pane을 직접 확인해 주세요."

## Notes

- `tmux send-keys -l` sends the argument literally (no key-name interpretation), then a separate `tmux send-keys ... Enter` submits — the two-step is required because Gemini's composer doesn't auto-submit on text-only input.
- For prompts containing many special characters or very long content, prefer the `load-buffer` / `paste-buffer` approach — it bypasses the shell entirely and is faster than escaping.
- The `agent-team/` directory is created automatically if it doesn't exist.
- Result files accumulate in `agent-team/` — clean them up as needed.
