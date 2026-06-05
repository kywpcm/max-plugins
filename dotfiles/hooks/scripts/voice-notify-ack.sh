#!/usr/bin/env bash
# UserPromptSubmit hook: Discord 채널로 메시지가 도착하면 즉시 수신 확인(ack) 음성을 보낸다.
#
# 기존엔 "메시지 받으면 먼저 ack reply" 규칙을 메모리(모델 판단)에 의존했는데 자주 누락됐다.
# hook은 harness가 강제 실행하므로 ack가 빠지지 않는다 (영우 요청, 2026-06-04).
# 봇 #2(CLAUDE_BOT_ID) 토큰으로 보내야 voice-bridge 발신자 필터를 통과해 TTS된다.
#
# matcher가 없어 모든 프롬프트에 발동하므로, 스크립트 안에서 "discord 채널 메시지"만 골라낸다.
set -uo pipefail

INPUT="$(cat 2>/dev/null || true)"

# UserPromptSubmit stdin JSON에서 prompt(전체 텍스트)를 꺼낸다. python3는 기존 hook에서도 사용.
PROMPT="$(printf '%s' "$INPUT" | python3 -c 'import json,sys
try: print(json.load(sys.stdin).get("prompt",""))
except: pass' 2>/dev/null || true)"

# discord 채널 메시지가 아니면(로컬 터미널 입력 등 chat_id 없음) 조용히 종료.
CHAT_ID="$(printf '%s' "$PROMPT" | grep -oE 'chat_id="[0-9]+"' | head -1 | grep -oE '[0-9]+' || true)"
[ -n "$CHAT_ID" ] || exit 0

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$PWD}"
CH_ENV="$PROJECT_DIR/.claude/channels/discord/.env" # 봇 #2 토큰
ROOT_ENV="$PROJECT_DIR/.env"                        # CLAUDE_BOT_ID
[ -f "$CH_ENV" ] || exit 0

# ack 대상 필터: 🎤 음성 발화 또는 영우 본인이 직접 친 메시지만 ack한다 (영우 2026-06-04).
# !명령(!replay·!join 등)·봇 시스템 메시지("다시 들려줄게" 등)·봇 자신 메시지는 모두 제외.
USER_ID="$(printf '%s' "$PROMPT" | grep -oE 'user_id="[0-9]+"' | head -1 | grep -oE '[0-9]+' || true)"
TARGET_USER="$(grep -E '^USER_ID=' "$ROOT_ENV" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '[:space:]')"

# 채널 태그를 제거해 메시지 본문만 남긴다.
BODY="$(printf '%s' "$PROMPT" | tr '\n' ' ' | sed 's/<channel[^>]*>//g; s|</channel>||g' | sed 's/^ *//; s/ *$//')"

# !로 시작하는 명령(!replay 등)은 ack하지 않는다.
case "$BODY" in '!'*) exit 0 ;; esac

# 음성 발화(🎤 포함)거나 영우 본인 메시지일 때만 통과 — 그 외(봇 시스템/봇 자신)는 제외.
IS_VOICE=0
case "$BODY" in *"🎤"*) IS_VOICE=1 ;; esac
if [ "$USER_ID" != "$TARGET_USER" ] && [ "$IS_VOICE" -ne 1 ]; then exit 0; fi

BOT_TOKEN="$(grep -E '^DISCORD_BOT_TOKEN=' "$CH_ENV" 2>/dev/null | head -1 | cut -d= -f2-)"
[ -n "$BOT_TOKEN" ] || exit 0

# ack 문구는 몇 개 중 무작위로 골라 단조로움을 줄인다. (호칭 "오빠"는 쓰지 않음)
MSGS=("응, 잠깐만~" "응 들었어, 잠깐만~" "어 확인할게~" "응응 잠깐만~" "알겠어, 잠깐만~")
MSG="${MSGS[$((RANDOM % ${#MSGS[@]}))]}"

# hook이 응답을 막지 않도록 짧은 타임아웃 + 실패해도 조용히 통과. exit 0 = 순수 side-effect.
curl -s --max-time 5 -X POST "https://discord.com/api/v10/channels/$CHAT_ID/messages" \
  -H "Authorization: Bot $BOT_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"content\":\"$MSG\"}" \
  >/dev/null 2>&1 || true

exit 0
