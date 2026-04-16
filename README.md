# max-plugins

개인용 Claude Code 플러그인 마켓플레이스. 커스텀 스킬, 명령어, 설정, 훅을 패키징하여 다른 머신에서 동일한 Claude Code 환경을 구축할 수 있다.

## 포함 내용

### 플러그인 자동 로드 (dotfiles-claude-code)

| 유형 | 이름 | 설명 |
|------|------|------|
| 스킬 | `sync-env` | 라이브 환경을 max-plugins repo에 동기화 |
| 스킬 | `apply-env` | max-plugins repo로 환경 설치/업데이트 |
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
| `save-conv-before-commit.sh` | 커밋 전 대화 저장 훅 |

## 설치 방법

### 1. 마켓플레이스 등록 및 플러그인 설치

```bash
# 마켓플레이스 등록
claude plugin marketplace add --source github:kywpcm/max-plugins

# 플러그인 설치 (스킬, 명령어 자동 로드)
claude plugin install dotfiles-claude-code@max-plugins
```

### 2. dotfiles 설치

```bash
# 플러그인 캐시 디렉토리에서 install.sh 실행
cd ~/.claude/plugins/cache/max-plugins/dotfiles-claude-code/1.0.0
./install.sh
```

### 3. 수동 설정

- `~/.claude/channels/discord/.env` — `DISCORD_BOT_TOKEN=...` 추가
- `~/.claude/channels/discord/access.json` — `allowFrom`에 본인 Discord 유저 ID 추가
- `~/.claude/channels/telegram/.env` — `TELEGRAM_BOT_TOKEN=...` 추가
- `~/.claude/channels/telegram/access.json` — `allowFrom`에 본인 Telegram 유저 ID 추가
- `~/.claude/settings.json` — `enabledPlugins`를 실제 설치된 플러그인에 맞게 조정

## 업데이트

```bash
# 플러그인 업데이트
claude plugin update dotfiles-claude-code@max-plugins

# dotfiles 재적용
cd ~/.claude/plugins/cache/max-plugins/dotfiles-claude-code/<version>
./install.sh
```

## 라이선스

MIT
