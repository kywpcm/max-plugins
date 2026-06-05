#!/usr/bin/env bash
# PostToolUse hook: 2분 이상 침묵 시 진행 중 알림 + 도구 오류 즉시 알림.
# voice-notify.sh와 동일한 패턴 — BOT_TOKEN(봇 #2)으로 보내야 voice-bridge TTS 필터를 통과한다.
set -uo pipefail

INPUT="$(cat 2>/dev/null || true)"

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$PWD}"
CH_ENV="$PROJECT_DIR/.claude/channels/discord/.env"
ROOT_ENV="$PROJECT_DIR/.env"

[ -f "$CH_ENV" ] || exit 0

BOT_TOKEN="$(grep -E '^DISCORD_BOT_TOKEN=' "$CH_ENV" 2>/dev/null | head -1 | cut -d= -f2-)"
CHANNEL_ID="$(grep -E '^TEXT_CHANNEL_ID=' "$ROOT_ENV" 2>/dev/null | head -1 | cut -d= -f2-)"
[ -n "$BOT_TOKEN" ] && [ -n "$CHANNEL_ID" ] || exit 0

send_msg() {
  curl -s --max-time 5 -X POST "https://discord.com/api/v10/channels/$CHANNEL_ID/messages" \
    -H "Authorization: Bot $BOT_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"content\":\"$1\"}" \
    >/dev/null 2>&1 || true
}

# 도구 오류 감지: tool_response.error가 null이 아닌 경우
HAS_ERROR="$(printf '%s' "$INPUT" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    r = d.get('tool_response', {})
    print('yes' if r.get('error') else 'no')
except:
    print('no')
" 2>/dev/null || echo "no")"

if [ "$HAS_ERROR" = "yes" ]; then
  TOOL="$(printf '%s' "$INPUT" | sed -n 's/.*"tool_name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"
  send_msg "⚠️ ${TOOL:-도구} 오류 발생했어. 확인해봐."
  exit 0
fi

# 2분(120초) 쿨다운: 작업의 첫 도구 사용 시에는 타이머만 시작하고 알림 없음.
# 작업(턴)이 끝날 때마다 Stop hook이 이 파일을 지우므로(settings.json), 새 작업의
# 첫 도구는 항상 last=0 → 알림 스킵. 2분 이상 지속되는 긴 작업에서만 알림이 나간다.
LAST_FILE="/tmp/voice_bridge_progress_$(id -u)"
now=$(date +%s)
last=0
[ -f "$LAST_FILE" ] && last=$(cat "$LAST_FILE" 2>/dev/null || echo 0)

if [ "$last" = "0" ]; then
  echo "$now" > "$LAST_FILE"  # 타이머 시작, 알림은 보내지 않음
  exit 0
fi

if (( now - last < 120 )); then exit 0; fi
echo "$now" > "$LAST_FILE"

send_msg "⚙️ 작업 진행 중이야. 잠깐만 기다려"

exit 0
