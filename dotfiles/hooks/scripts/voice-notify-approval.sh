#!/usr/bin/env bash
# 음성 워크플로 프로젝트 전용 Notification hook.
#
# Claude Code가 "권한/승인 대기" 알림(Notification)을 띄울 때, voice-bridge가 읽는
# Discord 텍스트 채널에 메시지를 보낸다. voice-bridge가 TTS로 읽어줘서, 음성으로만
# 듣고 있는 사용자가 "막혀서 기다리는 중"임을 알 수 있다 (무한 펜딩 방지 안전망).
#
# 단, 단순 idle(입력 대기 60초) 알림은 진짜 펜딩이 아니라 그냥 잠깐 멈춘 것이므로
# 제외한다 — 음성 대화 중 자연스러운 멈춤마다 울리면 거슬리기 때문 (영우 요청, 2026-06-02).
#
# project-level(.claude/settings.json)에서만 등록한다 → 일반 프로젝트엔 영향 없음.
# 봇 #2(CLAUDE_BOT_ID) 토큰으로 보내야 voice-bridge의 발신자 필터를 통과해 TTS된다.
set -uo pipefail

# Notification hook은 stdin으로 JSON({"message": "...", ...})을 받는다.
INPUT="$(cat 2>/dev/null || true)"
MSG="$(printf '%s' "$INPUT" | sed -n 's/.*"message"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"

# idle 입력 대기 알림은 스킵. Claude Code의 idle 문구는 "...waiting for your input".
# (권한 알림은 "...needs your permission..."이라 이 패턴에 안 걸려 정상 전송된다.)
case "$MSG" in
  *"waiting for your input"*) exit 0 ;;
esac

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$PWD}"
CH_ENV="$PROJECT_DIR/.claude/channels/discord/.env" # 봇 #2 토큰 (DISCORD_BOT_TOKEN)
ROOT_ENV="$PROJECT_DIR/.env"                        # TEXT_CHANNEL_ID

# Discord 채널 설정이 없는 프로젝트면 조용히 종료 (이중 안전장치).
[ -f "$CH_ENV" ] || exit 0

# .env를 source하지 않고 해당 키만 추출 (다른 비밀값 로드 부작용 방지).
BOT_TOKEN="$(grep -E '^DISCORD_BOT_TOKEN=' "$CH_ENV" 2>/dev/null | head -1 | cut -d= -f2-)"
CHANNEL_ID="$(grep -E '^TEXT_CHANNEL_ID=' "$ROOT_ENV" 2>/dev/null | head -1 | cut -d= -f2-)"
[ -n "$BOT_TOKEN" ] && [ -n "$CHANNEL_ID" ] || exit 0

# hook이 Claude Code를 막지 않도록 타임아웃을 짧게, 실패해도 조용히 통과.
curl -s --max-time 5 -X POST "https://discord.com/api/v10/channels/$CHANNEL_ID/messages" \
  -H "Authorization: Bot $BOT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content":"⏸️ Claude Code가 승인을 기다리고 있어요. 확인해주세요."}' \
  >/dev/null 2>&1 || true

exit 0
