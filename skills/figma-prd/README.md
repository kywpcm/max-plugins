# figma-prd

Figma 기획서 노드들에서 결정적 텍스트·이미지를 추출하고 코딩 에이전트 입력용 PRD 마크다운으로 정제하는 Claude Code 스킬.

자세한 사용법·동작은 `SKILL.md` 참조.

## 디렉터리

```
figma-prd/
├── SKILL.md                              # 스킬 정의 (트리거·워크플로·사용법)
├── README.md                             # 이 파일
├── scripts/
│   ├── extract.py                        # Figma REST API → texts.md([변경]/[추가]/[수정] 태그)/comments.md/images/screenshot
│   └── synthesize.py                     # texts + analysis → 최종 prd.md
├── prompts/
│   ├── analyze.backend.md                # 서브에이전트 백엔드 분석 프롬프트
│   └── analyze.frontend.md               # 서브에이전트 프론트엔드 분석 프롬프트
└── templates/
    ├── config.example.json
    ├── prd.backend.template.md
    └── prd.frontend.template.md
```

## 사전 준비

- `FIGMA_TOKEN` 환경 변수 (Figma Personal Access Token)
- Python 3.10+ (표준 라이브러리만 사용)
- `ANTHROPIC_API_KEY` **불필요** — 멀티모달 분석은 Claude Code Agent 도구로 수행

## 빠른 시작

```bash
export FIGMA_TOKEN=figd_...
cp ~/.claude/plugins/.../figma-prd/templates/config.example.json ./figma-prd.config.json
# config 편집 후
/figma-prd --config figma-prd.config.json
```

## 파이프라인

1. `extract.py` — REST API로 노드 트리·텍스트·이미지 수집 (결정적). "변경"/"추가"/"수정" 박스를 geometry로 감지해 콘텐츠에 `[변경]`/`[추가]`/`[수정]` 태그를 달고, 노드 관련 댓글 스레드를 `comments.md`로 수집.
2. Agent 서브에이전트 — 노드별 모드별 멀티모달 분석 (병렬 가능). 변경 마커·댓글을 반영.
3. `synthesize.py` — 텍스트 + 분석 결과 → PRD 마크다운 합성 (상단 `변경·추가·수정 요약` 섹션 포함)
