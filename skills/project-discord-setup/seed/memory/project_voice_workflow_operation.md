---
name: voice-workflow-operation
description: 음성 워크플로 운영 규칙 — bypassPermissions + plan 모드 끄기 (plan 승인은 원격 해소 불가)
metadata:
  type: project
---

음성 워크플로(운전 중 음성으로 Claude Code 작업)에선 봇 #2 Claude Code를 **bypassPermissions 모드 + plan 모드 끄고** 운영해야 한다.

**Why:** plan 승인 모달(ExitPlanMode "Would you like to proceed?")은 Claude Code 로컬 UI 키 입력(1/2/3)만 받는다. Discord 텍스트/음성으로 "승인"이라 해도 큐잉만 될 뿐 모달을 못 풀어 **무한 펜딩(데드락)**이 된다. 원격 승인 공식 방법은 없다.

**How to apply:** 음성 작업 시 plan 모드 켜지 말 것. 권한은 bypassPermissions로 자동 처리. 입력/승인 대기가 생기면 [[notification-hook-voice-alert]]가 음성으로 알린다.
