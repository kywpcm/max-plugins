---
name: figma-prd
description: >
  Figma 기획서 노드들에서 결정적(deterministic) 텍스트와 이미지를 추출하고,
  코딩 에이전트 입력용 PRD 마크다운으로 정제합니다.
  Figma REST API를 진실 공급원으로 사용하고, 래스터 이미지(순서도 등)는
  서브에이전트 멀티모달 분석으로 의미를 추출합니다.
  Trigger on "figma prd", "피그마 PRD", "피그마 기획서 PRD", "Figma 노드 PRD 추출",
  "기획 문서 정제", "백엔드 요구사항 추출", "프론트엔드 요구사항 추출",
  "extract prd from figma", "/figma-prd".
  스킬 호출 시 mode(backend|frontend|both)와 추출 대상 노드 목록을 받아
  해당 모드의 요구사항만 정제합니다. 매번 새로 추출하기보다 config 파일로
  재사용하도록 설계되어 있으며, Figma 버전이 올라가면 동일 config로 재실행하면 됩니다.
user-invocable: true
version: 0.2.0
---

# figma-prd

Figma 기획서 → PRD 마크다운 정제 스킬.

**최종 PRD는 코딩 에이전트가 구현 plan을 짜기 위한 입력 문서**다. 정확성·풍부함이 최우선이며, 가공·요약은 최소화한다.

## 핵심 설계

- **진실 공급원**: Figma REST API (`/v1/files/{key}/nodes`). MCP는 가공·요약 위험이 있어 본문 데이터로 안 씀.
- **래스터 이미지**: `/v1/images`로 PNG 렌더링 → 노드별 **서브에이전트**(`Agent` 도구)에게 멀티모달 분석 위임.
  - 별도 `ANTHROPIC_API_KEY` 불필요. Claude Code 구독 안에서 동작.
  - 메인 컨텍스트에는 짧은 보고만 돌아옴 → 노드 수가 많아도 안전.
- **모드 분기**: `backend | frontend | both`. 모드별로 분석 프롬프트·PRD 템플릿이 다름.
- **노드별 제외**: `exclude_node_ids`로 트리 가지치기 + `exclude_notes` 자연어 사유 첨부.
- **변경/추가 표시 결정적 추출**: "변경"·"추가" 라벨 TEXT 노드의 주석 박스 영역(bbox)을 찾아, 그 안에 들어가는 콘텐츠 텍스트에 `[변경]`/`[추가]` 태그를 단다(색/fill 판정이 아니라 라벨 일치 + geometry 겹침이라 결정적). PRD 상단에 `## 변경·추가 요약` 섹션으로 취합 → 코딩 에이전트가 변경분을 우선 인지. 라벨은 `change_labels`로 override.
- **댓글 수집**: `/v1/files/{key}/comments`를 파일당 1회 호출해 노드 서브트리에 앵커된 스레드(해결/미해결 모두, `[RESOLVED]` 표기)를 `comments.md`로 직렬화. (a) **서브에이전트 입력**으로 분석에 반영되고, (b) PRD 노드 섹션의 **`관련 댓글 (Figma)` 하위 섹션에 원문이 결정적으로 직접 수록**된다(LLM 누락 방지). 디자인 본문엔 없는 최신 결정·변경 논의를 포착.
- **숨김 노드(`hidden=true`) 자동 필터링** ("디스크립션입니다." 같은 placeholder 방지).
- **PRD 본문은 `analysis.{mode}.md` 중심**: 서브에이전트가 정제한 분석 결과만 PRD에 포함된다. 원본 `texts.md`는 디스크에 남아 서브에이전트 입력·디버깅·검증 용도로만 쓰이고, PRD 본문에는 raw로 들어가지 않는다. 디자인 시스템 데모·푸터 같은 UI 트리 가비지는 자연스럽게 PRD에서 제외된다.
- **페이지 메타 분리 (고정 동작)**: 디자인 메타(`page info` 프레임 — project/date/author/screen/screen id)는 별도 페이지 메타로 추출되어 노드 디렉터리 `page_info.json` + PRD 노드 섹션 상단 "페이지 메타" 한 줄에 표시.
- **재실행 친화**: config 파일로 입력을 고정해 Figma 버전 갱신 시 동일 명령으로 재추출 가능.

## 사용법

### 방식 A — config 파일 (재사용·권장)

```bash
export FIGMA_TOKEN=figd_xxx   # Figma 계정 설정 → Personal access tokens

# 프로젝트 루트(예: ~/workspace/your-project/)에 figma-prd.config.json 작성.
# 결과 PRD는 자동으로 <project_root>/docs/prd-out/ 에 생성된다.
/figma-prd
# 또는 명시적으로:
/figma-prd --config figma-prd.config.json
```

`--config` 인자가 없으면 cwd → git 프로젝트 루트 순으로 `figma-prd.config.json`을 자동 탐색한다.

### 방식 B — 대화형 (탐색·일회성)

```bash
/figma-prd
# Claude가 다음을 순서대로 물어봄:
#   1) mode (backend/frontend/both)
#   2) Figma 파일 URL 또는 file_key
#   3) 추출 대상 노드 URL 목록
#   4) 노드별 제외 지시 (선택)
#   5) 출력 디렉터리
# 마지막에 "이 입력을 config 파일로 저장할까요?" 안내
```

## config 스키마

```json
{
  "mode": "backend",                          // "backend" | "frontend" | "both"
  "file_key": "2CqOVKu1KasCF5K2hDWN2G",
  "task_name": "로그인 및 인증",                 // 결과 디렉터리 이름. 생략 시 file_key 사용.
  "context": "프로젝트 컨텍스트 한 줄 — PRD 헤더에 들어감",
  "change_labels": ["변경", "추가"],          // 선택. 변경 박스 라벨. 생략 시 기본 ["변경","추가"]
  "nodes": [
    {
      "id": "1518:57004",                     // node-id의 "-"는 ":"로 변환
      "label": "사용자 관리 정책",
      "exclude_node_ids": ["1518:57009"],     // 결정적 제외
      "exclude_notes": ["블록 1: 천안시민 — 스코프 외"]  // LLM 보조 안전망
    },
    { "id": "1518:57204", "label": "로그인 순서도" }
  ]
}
```

`templates/config.example.json`을 복사해 시작.

### 경로 규약

- **config 위치**: 작업 프로젝트 루트의 `figma-prd.config.json`. 인자 생략 시 cwd → git 루트 순으로 자동 탐색.
- **output_dir 기본값**: `<project_root>/docs/prd-out` (config에 `output_dir`를 명시하지 않으면 이 경로 사용).
- **`output_dir` 명시 시**:
  - 절대 경로 → 그대로 사용.
  - 상대 경로 → config 파일이 있는 디렉터리 기준으로 해석 (cwd 아님).
- **`task_name`**: 결과 디렉터리 이름. 동일 Figma 파일을 작업 의미 단위(예: "로그인 및 인증", "사용자 관리")로 구분할 때 사용. 생략하면 `file_key`로 fallback (하위 호환). 최종 경로는 `{output_dir}/{task_name 또는 file_key}/`.
- **권장**: `.gitignore`에 `docs/prd-out/` 추가. PRD는 자동 생성물이라 commit 대상이 아닌 경우가 일반적.

## 모드별 추출 내용

### backend 모드
- REST API 엔드포인트 후보 (method, path, request/response)
- 데이터 모델 후보 (엔티티·컬럼·관계·제약·인덱스)
- 외부 시스템 연동 (인터페이스 ID, 호출 시점, 데이터 흐름)
- 비즈니스 규칙·임계치 (예: 로그인 실패 5회, 휴면 90일)
- 권한·인증 (역할, 세션, 토큰)
- 트랜잭션 경계·동시성
- 배치/스케줄 (주기, 시각, 분산 잠금)
- 에러 코드·메시지
- 암호화·보안 정책 (알고리즘, 파기 주기)
- 수용 기준 후보 (Given/When/Then 또는 동사 글머리표)

### frontend 모드
- 화면 컴포넌트 인벤토리 (입력/버튼/모달/체크박스/라디오/리스트 등)
- 컴포넌트 상태 (default/hover/focus/error/disabled/loading)
- 인터랙션 플로우 (클릭→이동, 입력→유효성, 제출→결과)
- 유효성/에러 메시지
- 라우팅·이동 관계 (화면ID 상호 참조 보존)
- 반응형·접근성 단서
- 수용 기준 후보

### both 모드
같은 노드를 두 모드로 각각 분석. 출력 파일이 `.backend.analysis.md`/`.frontend.analysis.md`로 분리.

## 워크플로 (스킬 컨트롤러 동작)

1. **인자 파싱**
   - `--config <path>` 또는 대화형 입력으로 mode/file_key/output_dir/nodes 확정.
   - `FIGMA_TOKEN` 환경 변수 누락 시 즉시 안내 후 종료.

2. **추출 단계 — `extract.py` 실행**
   ```bash
   python3 ${SKILL_DIR}/scripts/extract.py \
     --config <config.json> \
     [--include-hidden]
   ```
   각 노드별로 다음을 생성 (`{task_name 또는 file_key}` 는 config에서 결정):
   ```
   {output_dir}/{task_name 또는 file_key}/{node_id_safe}/
     tree.json            # /v1/files/{k}/nodes 원본
     texts.md             # 부모 frame 계층 + 굵은 글씨 헤더 추론 ([변경]/[추가] 마커 포함)
     comments.md          # 노드 서브트리에 앵커된 댓글 스레드 (있을 때만)
     screenshot.png       # 노드 전체 스냅샷
     images/
       {image_node_id}.png
   ```

3. **분석 단계 — Agent 도구 dispatch (노드별 1회)**
   각 노드에 대해 `Agent(subagent_type=general-purpose)` 호출.
   프롬프트 본체는 `prompts/analyze.{mode}.md`를 읽어 그대로 사용하되, 다음 변수만 치환:
   - `{{NODE_LABEL}}`
   - `{{NODE_DIR}}` (절대 경로)
   - `{{EXCLUDE_NOTES}}`
   - `{{CONTEXT}}`

   서브에이전트는 디렉터리 내 `texts.md`·`screenshot.png`·`images/*.png`·`comments.md`(있으면)를 Read로 읽고 모드별 분석을 수행한다. `texts.md`의 `[변경]`/`[추가]` 마커와 댓글의 결정·변경 논의를 분석에 반드시 반영한다. 결과 처리는 다음 순서로:
   1. **1순위**: `Write` 도구로 `{node_dir}/analysis.{mode}.md` 에 직접 저장 → 메인에는 짧은 요약 보고만 반환 (메인 컨텍스트 보호).
   2. **fallback**: 환경 권한 정책으로 Write가 차단되면 분석 마크다운 본문 전체를 반환. 본문 외 군더더기(설명·코드펜스) 없이 `#### ` 시작 헤딩(체크리스트 첫 항목)부터 시작하는 마크다운 그대로 반환. 노드 메타 헤더는 만들지 않음 (PRD 합성 시 노드 섹션 상단에 이미 표시되므로 중복 금지).

   메인 컨트롤러는 각 Agent 응답 처리:
   - Bash 또는 Read로 `{node_dir}/analysis.{mode}.md` 존재 여부 확인.
   - 파일이 있으면 통과.
   - **없으면 Agent 응답 본문에서 첫 `#### ` 시작 라인부터 본문 끝까지 추출해 메인에서 `Write` 로 저장**. 이 fallback 덕에 서브에이전트 Write 차단 환경에서도 일관 동작.

   노드들이 독립적이므로 **한 메시지에 여러 Agent 호출**로 병렬 처리한다 (모드가 `both`면 노드당 2개).

4. **합성 단계 — `synthesize.py` 실행**
   ```bash
   python3 ${SKILL_DIR}/scripts/synthesize.py \
     --config <config.json>
   ```
   `texts.md` + 각 노드의 `analysis.{mode}.md`를 `templates/prd.{mode}.template.md` 골격에 채워 `{output_dir}/{task_name 또는 file_key}/prd.md` (또는 `prd.backend.md`/`prd.frontend.md`)로 합성.

5. **마무리**
   - 결과 경로 안내.
   - 검증 체크리스트 출력 (제외 노드가 본문에 없는가 / 모드별 핵심 항목이 들어있는가 / 이미지 첨부가 깨지지 않았는가 / `변경·추가 요약`이 Figma 변경 박스와 일치하는가).

## 인증

- **Figma Personal Access Token** (필수): 다음 두 곳 중 하나에 두면 됨. 우선순위는 env > config.
  1. 환경 변수 `FIGMA_TOKEN` — 셸에 `export FIGMA_TOKEN=figd_...` 또는 `~/.zshrc`에 영구 등록. 모든 프로젝트에서 공유 가능.
  2. config의 `figma_token` 필드 — 프로젝트별 토큰을 박아둘 때. config 파일은 `.gitignore`에 넣어 commit 금지.
  - 발급: Figma 웹 → 우측 상단 아바타 → Settings → Account → Personal access tokens → Generate new token.
  - 권한: 읽기 전용으로 충분.
- `ANTHROPIC_API_KEY`: **불필요**. 멀티모달 분석은 Claude Code Agent 도구 사용.

## 결과물 구조

```
{output_dir}/{task_name 또는 file_key}/
├── {제목} (backend).md                       # 모드 single, 예: "천안형GPT 사용자 관리·로그인 흐름 (backend).md"
├── {제목} (backend).md + {제목} (frontend).md # 모드 both
└── {node_id_safe}/
    ├── tree.json
    ├── texts.md                             # [변경]/[추가] 마커 포함
    ├── comments.md                          # 노드 관련 댓글 스레드 (있는 노드만)
    ├── page_info.json                       # 페이지 메타 (있는 노드만)
    ├── screenshot.png
    ├── images/
    │   ├── {image_node_id}.png
    │   └── {image_node_id}.analysis.{mode}.md
    └── analysis.{mode}.md                   # 노드 전체에 대한 모드별 분석
```

**PRD 파일명 자동 도출**:
1. `context`의 첫 마침표/줄바꿈 전 부분 → 제목.
2. context가 비었으면 첫 노드 라벨 (`+ 외 N건`).
3. 둘 다 없으면 `PRD`.

파일 시스템 금지 문자(`\\/:*?"<>|`)는 `_`로 치환. config 옵션으로 파일명 override는 없음 (자동만).

## 자주 묻는 것

**Q. Figma 버전이 갱신되면?**
A. 같은 config로 `/figma-prd --config figma-prd.config.json` 다시 실행. 기존 출력은 덮어쓰여진다.

**Q. 노드 ID는 어디서 구하나?**
A. Figma 디자인 노드 URL의 `node-id=A-B`에서 `A:B`로 변환. URL 그대로 넣어도 스킬이 파싱한다.

**Q. 일부 노드만 다시 처리하려면?**
A. config의 `nodes` 배열을 줄이거나, 추출 결과 디렉터리에서 해당 노드만 남기고 `synthesize.py`만 재실행.

**Q. 분석 정확도가 떨어진다면?**
A. config의 `context` 필드를 더 구체적으로 작성하거나 `exclude_notes`에 도메인 힌트를 추가. 분석 프롬프트(`prompts/analyze.{mode}.md`)를 직접 수정해도 됨.
