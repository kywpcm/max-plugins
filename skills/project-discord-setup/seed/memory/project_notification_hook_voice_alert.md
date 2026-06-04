---
name: notification-hook-voice-alert
description: Claude Code 작업 중 Discord 음성 알림 hook 4종 (voice-notify-approval.sh, voice-notify-progress.sh, voice-notify-ack.sh, Stop)
metadata:
  type: project
---

Claude Code hooks → Discord 텍스트 채널 → voice-bridge TTS로 상황 음성 알림. 스크립트는 `~/.claude/hooks/scripts/`에 위치하며, 봇 #2 토큰으로 보내야 voice-bridge의 `CLAUDE_BOT_ID` 필터를 통과해 TTS된다.

## 등록된 hook 스크립트
1. **voice-notify-approval.sh** (Notification hook): 권한/승인 대기 시 알림. idle "waiting for input"은 제외. 무한 펜딩 방지 안전망.
2. **voice-notify-progress.sh** (PostToolUse hook): 2분 쿨다운 "진행 중" 알림 + 도구 오류 즉시 알림. `/tmp/voice_bridge_progress_$(id -u)` 파일로 쿨다운 추적. 작업 첫 도구는 알림 없이 타이머만 시작, 2분 이상 지속되는 긴 작업에서만 알림.
3. **voice-notify-ack.sh** (UserPromptSubmit hook): Discord 채널 메시지 도착 시 즉시 수신 ack 음성 전송. stdin `prompt`에서 `chat_id` 파싱 → 봇 #2 토큰으로 ack. 스크립트 내 필터: **🎤 음성 발화 또는 영우 본인(`user_id == USER_ID`) 메시지만 ack**, `!`명령(!replay·!join 등)·봇 시스템/자신 메시지는 제외. [[feedback-discord-ack]]의 수동 ack 규칙을 자동화한 것.
4. **Stop hook** (inline, settings.json): 매 작업(턴) 종료 시 `rm -f /tmp/voice_bridge_progress_$(id -u)`로 타이머 초기화. 없으면 이전 타임스탬프가 남아 새 작업 첫 도구에서 "2분 경과" 오판정으로 알림이 잘못 나간다.

## 프로젝트 등록 방법
프로젝트 `.claude/settings.json`에 해당 hook type 추가 (UserPromptSubmit + Notification + PostToolUse + Stop). `.claude/channels/discord/.env` 없는 프로젝트는 조용히 스킵된다.

## 환경 요구사항
- 프로젝트 `.claude/channels/discord/.env`: `DISCORD_BOT_TOKEN`(봇 #2)
- 프로젝트 루트(또는 envs) `.env`: `TEXT_CHANNEL_ID`

관련: [[voice-workflow-operation]], [[feedback-discord-ack]]
