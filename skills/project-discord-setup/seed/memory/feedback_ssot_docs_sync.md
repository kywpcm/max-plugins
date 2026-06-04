---
name: ssot-docs-sync
description: SSOT 관점에서 소스코드 수정 시 관련 문서를 반드시 현행화해야 한다는 규칙
metadata:
  type: feedback
---

소스코드를 수정하면 그 내용을 기술한 문서(`docs/todo/improvements.md`, ADR, CLAUDE.md 등)도 반드시 같이 현행화한다.

**Why:** 문서는 SSOT(Single Source of Truth) 관점에서 코드의 현재 상태를 반영해야 한다. 코드만 바뀌고 문서가 낡으면 이후 세션·음성 요청에서 잘못된 전제로 작업하게 된다.

**How to apply:** 코드 변경 작업을 마무리할 때 해당 변경이 언급된 문서를 확인하고 함께 갱신한다. IMP/ADR 항목과 관련된 수정이면 상태 갱신(완료 항목 정리, 파라미터 현재값 반영)을 같은 커밋/턴에서 처리한다. [[project-todo-docs]]
