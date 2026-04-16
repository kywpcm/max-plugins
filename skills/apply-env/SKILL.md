---
name: apply-env
description: >
  max-plugins repo를 사용하여 현재 머신에 Claude Code 환경을 적용합니다.
  새 머신에서 동일한 Claude Code 환경을 구축하거나, 기존 머신의 환경을
  최신 repo 상태로 업데이트할 때 사용합니다.
  "환경 적용", "apply env", "새 머신 설정", "dotfiles 적용", "env apply",
  "환경 설치", "환경 구축", "클로드 코드 설정", "dotfiles install",
  "max-plugins 설치", "max-plugins 적용", "새 컴퓨터 설정",
  "다른 머신에서 적용", "환경 복원" 시 사용합니다.
  max-plugins repo를 처음 설치하거나 업데이트할 때 반드시 사용하세요.
user-invocable: true
version: 0.1.0
---

# apply-env

max-plugins repo를 사용하여 현재 머신에 Claude Code 환경을 설치하거나 업데이트한다. 새 머신에서의 초기 설정과 기존 머신의 업데이트를 모두 지원한다.

## Workflow

### Step 1: 현재 상태 진단

먼저 이 머신에 이미 max-plugins가 설치되어 있는지 확인한다.

```bash
# max-plugins repo가 이미 클론되어 있는지 확인
REPO_DIR=$(find ~/workspace ~/projects ~ -maxdepth 3 -type d -name "max-plugins" 2>/dev/null | head -1)

# 플러그인이 설치되어 있는지 확인
ls ~/.claude/plugins/cache/max-plugins/ 2>/dev/null

# 마켓플레이스가 등록되어 있는지 확인
cat ~/.claude/plugins/known_marketplaces.json 2>/dev/null | grep -q "max-plugins"
```

결과에 따라 모드를 결정한다:
- **초기 설치**: repo도 없고, 플러그인도 없는 상태 → Step 2부터
- **업데이트**: repo가 있고, 플러그인이 설치된 상태 → Step 4부터

### Step 2: 사전 요구사항 확인 (초기 설치 시)

```bash
# git 설치 확인
git --version

# claude CLI 설치 확인
claude --version

# terminal-notifier 설치 확인 (macOS 알림 훅용)
which terminal-notifier || echo "terminal-notifier 미설치 — brew install terminal-notifier"

# jq 설치 확인 (훅 스크립트용)
which jq || echo "jq 미설치 — brew install jq"
```

미설치된 도구가 있으면 설치 명령어를 안내한다. macOS가 아닌 경우 `terminal-notifier` 대신 해당 OS의 알림 도구를 안내한다.

### Step 3: repo 클론 (초기 설치 시)

```bash
# 기본 위치에 클론
mkdir -p ~/workspace
git clone git@github.com:kywpcm/max-plugins.git ~/workspace/max-plugins
REPO_DIR=~/workspace/max-plugins
```

SSH 인증 실패 시 HTTPS로 대안 제시:
```bash
git clone https://github.com/kywpcm/max-plugins.git ~/workspace/max-plugins
```

### Step 4: repo 최신화

```bash
cd "$REPO_DIR"
git pull origin master
```

### Step 5: 마켓플레이스 등록 및 플러그인 설치

사용자에게 아래 명령어를 실행하도록 안내한다. `claude plugin` 명령은 대화형이라 사용자가 직접 터미널에서 실행해야 한다.

```
아래 명령어를 터미널에서 직접 실행해 주세요:

# 마켓플레이스 등록 (이미 등록된 경우 건너뜀)
claude plugin marketplace add --source github:kywpcm/max-plugins

# 플러그인 설치 (이미 설치된 경우 업데이트)
claude plugin install dotfiles-claude-code@max-plugins
```

사용자가 실행을 완료하면 다음 단계로 진행한다.

### Step 6: dotfiles 설치 (install.sh 실행)

```bash
# 플러그인 캐시에서 install.sh 위치 찾기
INSTALL_SH=$(find ~/.claude/plugins/cache/max-plugins -name "install.sh" -type f 2>/dev/null | head -1)

# 또는 로컬 repo에서 직접 실행
if [ -z "$INSTALL_SH" ]; then
  INSTALL_SH="$REPO_DIR/install.sh"
fi

bash "$INSTALL_SH"
```

install.sh가 설치하는 항목:
- `CLAUDE.md` — 한국어 응답, 상태 알림 규칙
- `settings.json` — 권한, 훅, 플러그인 설정
- `statusline-command.sh` — tmux 상태줄 스크립트
- 훅 스크립트 — 위험 명령어 차단, 커밋 전 대화 저장
- 플러그인 메타데이터 — installed_plugins.json, known_marketplaces.json, blocklist.json
- 채널 접근 설정 — Discord/Telegram access.json (기존 파일이 없을 때만)

### Step 7: 수동 설정 안내

install.sh 완료 후 사용자에게 수동 설정이 필요한 항목을 안내한다.

**채널 설정 (사용하는 채널만):**

Discord:
```bash
# 1. 봇 토큰 설정
echo "DISCORD_BOT_TOKEN=여기에_봇_토큰" > ~/.claude/channels/discord/.env

# 2. 유저 ID 설정 — access.json의 allowFrom에 본인 Discord 유저 ID 추가
# 예: "allowFrom": ["123456789012345678"]
```

Telegram:
```bash
# 1. 봇 토큰 설정
echo "TELEGRAM_BOT_TOKEN=여기에_봇_토큰" > ~/.claude/channels/telegram/.env

# 2. 유저 ID 설정 — access.json의 allowFrom에 본인 Telegram 유저 ID 추가
# 예: "allowFrom": [8505525944]
```

**플러그인 설정:**
```
settings.json의 enabledPlugins에서 실제 사용하지 않는 플러그인은 false로 변경하거나 제거할 수 있습니다.
```

### Step 8: 설치 검증

설치가 올바르게 되었는지 확인한다:

```bash
# settings.json 존재 확인
[ -f ~/.claude/settings.json ] && echo "✅ settings.json" || echo "❌ settings.json"

# CLAUDE.md 존재 확인
[ -f ~/.claude/CLAUDE.md ] && echo "✅ CLAUDE.md" || echo "❌ CLAUDE.md"

# 훅 스크립트 존재 및 실행 권한 확인
[ -x ~/.claude/hooks/scripts/block-dangerous.sh ] && echo "✅ block-dangerous.sh" || echo "❌ block-dangerous.sh"
[ -x ~/.claude/hooks/scripts/save-conv-before-commit.sh ] && echo "✅ save-conv-before-commit.sh" || echo "❌ save-conv-before-commit.sh"

# 상태줄 스크립트 확인
[ -f ~/.claude/statusline-command.sh ] && echo "✅ statusline-command.sh" || echo "❌ statusline-command.sh"

# 플러그인 메타데이터 확인
[ -f ~/.claude/plugins/installed_plugins.json ] && echo "✅ installed_plugins.json" || echo "❌ installed_plugins.json"

# 채널 설정 확인
for ch in discord telegram; do
  [ -f ~/.claude/channels/$ch/access.json ] && echo "✅ $ch access.json" || echo "⚠️ $ch access.json (미설정)"
done
```

### Step 9: 완료 보고

설치/업데이트 결과를 요약하고, 수동 설정이 필요한 항목이 있으면 다시 한번 안내한다.

```
환경 적용이 완료되었습니다.

⚠️ 수동 설정 필요:
  - Discord: ~/.claude/channels/discord/.env 에 봇 토큰 추가
  - Telegram: ~/.claude/channels/telegram/.env 에 봇 토큰 추가

환경을 변경한 후 repo에 반영하려면: /sync-env
```
