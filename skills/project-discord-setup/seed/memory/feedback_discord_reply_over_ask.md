---
name: discord-reply-over-ask
description: 원격(Discord) 턴에선 AskUserQuestion·plan 모달 같은 로컬 UI 대신 reply로 선택지를 보내고 사용자의 다음 메시지로 결정을 처리 — DM·음성 공통
metadata:
  type: feedback
---

디스코드 채널(DM·텍스트·음성)에서 온 턴(`<channel source="discord" …>` 태그 / `chat_id` 있음)을 처리할 땐, 사용자 결정이 필요해도 `AskUserQuestion`이나 plan 승인 모달 같은 **로컬 인터랙티브 UI를 띄우지 않는다**. 대신 선택지를 **`reply`로 디스코드 채널에 텍스트로 보내고**, 사용자의 다음 디스코드 메시지(프롬프트로 도착)를 답으로 받아 선택을 처리한다.

**Why:** `AskUserQuestion`·`ExitPlanMode` 같은 모달은 Claude Code **로컬 UI 키 입력(1/2/3)만** 받는다. 디스코드 원격 사용자는 그 키를 누를 수 없어, 디스코드로 "1번"이라 답해도 모달이 안 풀리고 **무한 펜딩(데드락)**이 된다. reply→프롬프트 경로가 원격에서 결정을 받는 유일한 길이다.

**How to apply:**
- 선택지는 reply에 짧은 번호 목록으로: `1) … 2) … 3) … — 번호나 내용으로 답해줘`. 사용자의 다음 메시지(번호 또는 텍스트)를 파싱해 선택을 확정한다.
- 예/아니오 확인도 모달 대신 reply로 묻는다(`진행할까? 예/아니오`).
- 도구 권한 프롬프트는 `bypassPermissions`(`clauded`)로 운영해 애초에 안 뜨게 하고, plan 모드는 원격 세션에서 켜지 않는다(ExitPlanMode 모달이 원격에서 안 풀린다).
- 로컬 터미널 턴(`chat_id` 없음 — 화면을 직접 봄)은 `AskUserQuestion`을 평소대로 써도 된다. 이 규칙은 **원격 디스코드 턴 전용**이다.

ack·알림 동작은 [[feedback-discord-ack]], [[notification-hook-voice-alert]].
