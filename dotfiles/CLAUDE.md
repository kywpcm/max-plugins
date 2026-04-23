- 모든 세션에서 너가 한국어로 대답해 주길 원해.

## Status Announcements
- 도구, 스킬, 에이전트를 사용할 때 🥕 이모티콘과 함께 현재 상황을 간단히 알려줘.
- 형식: 🥕 Using [도구/스킬/에이전트명] to [간단한 설명].
- 한 문장으로 짧게.
- Examples:
  - 🥕 Using Explore agent to check the current project state.
  - 🥕 Using firecrawl skill to crawl and learn from the website.

## Response Length (응답 길이)
- 답변은 짧고 요약적으로. 장황한 설명은 지양.
- 핵심 정의 + 필요한 예시 1개 수준으로 압축. 여러 섹션, 중복 설명, 긴 비교표, 불필요한 코드 예시는 자제할 것.
- explanatory 모드의 `★ Insight` 섹션도 필요할 때만, 2-3개 포인트로 간결히
- 사용자가 답변을 읽고 이해하는 시간 자체가 작업 비용이라 간결함이 중요함 (2026-04-22 요청).
- 사용자가 명시적으로 "자세히", "설명해줘" 등 요청할 때만 길게 설명.

## Terminology (용어)
- 기술 용어는 **한국어 번역 + 괄호 안 원문** 형식으로 표기. 예: `외부화(externalization)`, `관찰성(observability)`, `의존성 주입(dependency injection)`.
- 단, **한국어 번역이 어색한 단어는 번역 없이 원문 그대로 사용**해도 됨. 예: `parsing`, `refactoring`, `framework`, `thread` 등 업계에서 원문이 더 자연스러운 경우.
- **약어(Acronym)는 첫 등장 시 풀 네임 병기**: MVCC, IX, IS, OLTP, DDL, DML, RDBMS 등 약어를 쓸 때는 처음 나올 때 풀 네임을 함께 표기해서 해당 용어를 모르는 상태에서도 이해 가능하도록 할 것. 형식: `MVCC(Multi-Version Concurrency Control)`, `OLTP(Online Transaction Processing)`, `IX(Intention eXclusive) 락`. 같은 응답 내 반복 등장 시에는 약어만 써도 됨 (2026-04-22 요청).
- 개별 용어 규칙:
  - "externalization" → **"외부화"**로 번역 (2026-04-22 요청). "외화"는 사용 금지.