---
name: feedback-discord-ack
description: 음성 채널 메시지 수신 확인(ack)은 voice-notify-ack.sh hook이 자동 전송 — 모델은 수동 ack reply 불필요(중복 방지)
metadata:
  type: feedback
---

수신 확인(ack)은 `voice-notify-ack.sh` (UserPromptSubmit hook)이 **자동 전송**한다 — Discord 채널로 메시지가 오면 harness가 즉시 ack 음성을 보낸다. 모델이 수동 ack에 의존하면 자주 누락돼 hook으로 강제화했다. 상세는 [[notification-hook-voice-alert]].

**모델이 할 일:** Discord 채널 메시지엔 **수동 ack reply를 보내지 않는다**(hook과 중복). 대신 바로 작업하고 **작업 결과·실제 응답·질문**만 reply로 보낸다. (로컬 터미널 입력은 chat_id가 없어 hook ack가 안 나가지만, 로컬은 화면을 보므로 ack 불필요.)

**Why:** 음성 채널 특성상 피드백이 늦으면 요청이 전달됐는지 알 수 없다 → hook 자동 ack로 해결.

빠른 피드백이 중요한 이유: Discord reply가 봇 #2 계정으로 전송 → BridgeListener → TTS로 재생되는 구조라, ack가 늦으면 TTS 피드백도 늦어진다.
