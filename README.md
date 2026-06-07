# max-plugins

개인용 Claude Code 플러그인 마켓플레이스. 커스텀 스킬, 명령어, 설정, 훅을 패키징하여 다른 머신에서 동일한 Claude Code 환경을 구축할 수 있다.

## 포함 내용

### 플러그인 자동 로드 (dotfiles-claude-code)

| 유형 | 이름 | 설명 |
|------|------|------|
| 스킬 | `reconcile-env` | 라이브 환경 ↔ repo **양방향 동기화**(받을 건 받고 올릴 건 올림). 단일 호출, 순서 신경 불필요 |
| 스킬 | `comment-code` | 코드에 한국어 주석 자동 추가 |
| 스킬 | `save-conversation` | 대화 요약을 마크다운으로 저장 |
| 명령어 | `feature-branch` | develop에서 feature 브랜치 생성 |
| 명령어 | `pull-all` | 로컬 브랜치 일괄 pull |
| 명령어 | `release` | git-flow release 진행 |

### install.sh로 수동 설치

| 파일 | 설명 |
|------|------|
| `CLAUDE.md` | 한국어 응답, 상태 알림 규칙 |
| `settings.json` | 권한, 훅, 플러그인 설정 |
| `statusline-command.sh` | tmux 상태줄 스크립트 |
| `block-dangerous.sh` | 위험 명령어 차단 훅 |

## 설치 / 사용

### 1. 새 머신 부트스트랩 (최초 1회, 수동)

스킬은 자신이 속한 플러그인을 설치할 수 없으므로, 새 머신에서는 이 2줄만 수동 실행한다:

```bash
claude plugin marketplace add --source github:kywpcm/max-plugins
claude plugin install dotfiles-claude-code@max-plugins
```

### 2. 환경 동기화 — `reconcile` 하나로

이후부터는 어느 머신에서든 **`reconcile-env` 스킬 하나만** 호출하면 된다 ("claude 환경 동기화/맞춰줘"). 호출 시:

- repo를 pull + `claude plugin update`로 최신 받기
- `~/.claude`와 repo를 3-way로 비교해 **받을 변경은 받고(pull) 올릴 변경은 올림(push)** — 진짜 충돌만 물어봄
- 올릴 게 있으면 버전 bump + 커밋 + push까지 자동

첫 실행(부트스트랩)은 `install.sh`로 환경 전체를 시드하고, 이후엔 변경분만 양방향 reconcile한다.

**모드 인자**: 없음=자동 양방향, `pull`=repo→라이브 강제(복구/새 머신), `push`=라이브→repo 강제(복구).

동기화 대상은 결정적 파일 4종(`settings.json` 5필드 / `CLAUDE.md` / `statusline-command.sh` / `hooks/scripts/*.sh`). `known_marketplaces.json`·`installed_plugins.json`은 Claude Code가 관리하는 파생 상태라 제외한다.

### 3. 머신별 관리 항목 (sync-exclude.json)

`dotfiles/sync-exclude.json`에 명시된 플러그인/채널은 reconcile 양방향에서 건드리지 않으며, **각 머신에서 따로 설치·설정**한다. 현재 대상: `discord@claude-plugins-official` 플러그인, `discord` 채널.

이 머신에서 Discord를 사용하려면 직접 설정한다:

```bash
claude plugin install discord@claude-plugins-official
echo "DISCORD_BOT_TOKEN=..." > ~/.claude/channels/discord/.env
# ~/.claude/channels/discord/access.json 의 allowFrom 에 본인 Discord 유저 ID 추가
```

제외 대상을 바꾸려면 `sync-exclude.json` 한 곳만 수정하면 reconcile 양방향에 반영된다.

## 라이선스

MIT
