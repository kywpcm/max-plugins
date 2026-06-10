#!/bin/bash
# Notification 훅 필터: 실제 권한 승인이 필요할 때만 알림을 보낸다.
# idle(입력 대기) 알림은 Stop 훅의 "작업 완료"와 중복되므로 억제한다.
#
# 구분 신호 우선순위:
#   1) notification_type 필드 (permission_prompt / idle_prompt) — 영어 enum이라 언어 설정 무관
#   2) message 텍스트 패턴 — notification_type 누락 시 폴백
# 정책: "idle로 확신될 때만 억제". 애매하면 알림을 보내 진짜 권한 알림을 놓치지 않는다.

INPUT=$(cat)

# terminal-notifier 없으면 조용히 종료
command -v terminal-notifier >/dev/null 2>&1 || exit 0

TYPE=$(echo "$INPUT" | jq -r '.notification_type // ""')
MESSAGE=$(echo "$INPUT" | jq -r '.message // ""')

# idle로 확신되면 억제 (notification_type 우선, 없으면 메시지 패턴 폴백)
if [ "$TYPE" = "idle_prompt" ] || echo "$MESSAGE" | grep -qiE "waiting for your input|is waiting|been idle|idle_prompt"; then
  exit 0
fi

# 그 외(실제 권한 요청 등)는 알림 발송
LABEL=$(tmux display-message -p -t "$TMUX_PANE" '#S / #I:#W / #P' 2>/dev/null)
terminal-notifier -title "Claude Code" -message "${LABEL} 권한 승인 필요" -sound Glass
exit 0
