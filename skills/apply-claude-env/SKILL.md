---
name: apply-claude-env
description: >
  max-plugins repo를 사용하여 현재 머신에 Claude Code 환경을 적용합니다.
  새 머신에서 동일한 Claude Code 환경을 구축하거나, 기존 머신의 환경을
  최신 repo 상태로 업데이트할 때 사용합니다.
  "claude 환경 적용", "apply claude env", "env apply",
  "새 머신 claude 설정", "claude 환경 설치", "claude 환경 구축",
  "클로드 코드 설정", "max-plugins 설치", "max-plugins 적용",
  "settings.json 복원", "CLAUDE.md 적용", "훅 스크립트 적용",
  "claude 환경 복원", "새 컴퓨터 claude 설정" 시 사용합니다.
  shell/터미널 dotfiles(.zshrc/.tmux.conf 등)가 아닌 Claude Code 환경 전용입니다.
  순수 dotfiles를 적용하려면 apply-dotfiles-env를 사용하세요.
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

### Step 4: workspace clone 최신화 (해당되는 경우만)

사용자가 `~/workspace/max-plugins` 같은 별도 경로에 repo를 clone해둔 경우에만 해당한다. Claude Code의 **플러그인 cache**(`~/.claude/plugins/cache/max-plugins/`)는 Step 5에서 따로 갱신하므로 이 단계는 독립적이다.

```bash
if [ -n "$REPO_DIR" ] && [ -d "$REPO_DIR/.git" ]; then
  cd "$REPO_DIR" && git pull --ff-only origin master
fi
```

`--ff-only`로 의도치 않은 머지 커밋을 막는다. fast-forward가 불가능하면 사용자에게 알린다. workspace clone이 없으면 이 단계는 건너뛰고, 플러그인 cache는 Step 5의 마켓플레이스 update가 최신화한다(= cache 기반 사용 시의 pull).

### Step 5: 마켓플레이스 및 플러그인 동기화

Step 1에서 진단한 상태에 따라 초기 설치 또는 업데이트를 실행한다. `claude plugin` CLI는 비대화형이므로 Bash tool로 직접 실행한다.

**케이스 A — 초기 설치** (마켓플레이스 미등록 또는 플러그인 미설치):

```bash
# 마켓플레이스 등록
claude plugin marketplace add --source github:kywpcm/max-plugins

# 플러그인 설치
claude plugin install dotfiles-claude-code@max-plugins
```

**케이스 B — 업데이트** (마켓플레이스 등록 + 플러그인 이미 설치):

```bash
# 마켓플레이스의 최신 메타데이터 pull
claude plugin marketplace update max-plugins

# 플러그인 업데이트 (새 version이 있으면 cache를 해당 버전으로 교체)
claude plugin update dotfiles-claude-code@max-plugins
```

**주의사항**:

- 두 명령 모두 실패할 수 있다 (네트워크, 인증, 권한 등). 실패 시 에러 원문을 사용자에게 보여주고 수동 실행을 권한다.
- `claude plugin update`는 "Restart to apply changes"를 출력한다 — **cache 파일 교체는 즉시**되지만 **현재 세션의 로드된 skill 목록은 재시작 전까지 구버전**이다. `/reload-plugins` 또는 새 세션 시작을 권장한다.
- `claude plugin update`가 "already at latest"라 하는데 분명히 GitHub에 신규 커밋이 있다면, **plugin.json의 version bump 누락**이 원인일 확률이 높다. 이 경우 repo에서 `/sync-claude-env`의 version bump 단계를 실행해야 한다.

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
- `CLAUDE.md` — 한국어 응답, 상태 알림 규칙 (전체 복사)
- `settings.json` — **`dotfiles/sync-fields.json`에 나열된 필드만 머지** (현재 `permissions` / `hooks` / `statusLine` / `enabledPlugins` / `extraKnownMarketplaces` 5개). 라이브의 다른 키(`effortLevel`, `channelsEnabled`, `skipDangerousModePermissionPrompt`, `skipAutoPermissionPrompt` 등 머신별 개인 설정)는 보존됨. 기존 파일은 `.bak`으로 백업. 동기화 대상을 바꾸려면 `sync-fields.json` 한 곳만 수정.
- `statusline-command.sh` — tmux 상태줄 스크립트 (전체 복사)
- 훅 스크립트 — 위험 명령어 차단 (전체 복사)
- 플러그인 메타데이터 — installed_plugins.json (제외 플러그인은 라이브 보존 머지), known_marketplaces.json (전체 복사)

**제외 대상 (`dotfiles/sync-exclude.json`):** 이 파일의 `plugins`/`channels`에 나열된 항목(현재 `discord@claude-plugins-official` 플러그인, `discord` 채널)은 sync/apply 어느 방향에서도 건드리지 않는다. discord는 각 머신에서 따로 설치·설정한다. `enabledPlugins`와 `installed_plugins.json`을 머지할 때 제외 플러그인의 **라이브 머신 상태는 그대로 보존**되며 repo가 추가/제거하지 않는다. 제외 대상을 바꾸려면 `sync-exclude.json` 한 곳만 수정한다.

### Step 7: 수동 설정 안내

install.sh 완료 후 사용자에게 수동 설정이 필요한 항목을 안내한다.

**플러그인 설정:**
```
settings.json의 enabledPlugins에서 실제 사용하지 않는 플러그인은 false로 변경하거나 제거할 수 있습니다.
```

**제외 플러그인/채널 (각 머신에서 직접 관리):**

`dotfiles/sync-exclude.json`에 명시된 항목(현재 discord)은 repo가 관리하지 않으므로, 이 머신에서 discord를 쓰려면 직접 설치·설정한다. (apply는 이미 설치된 discord를 보존만 하고 새로 깔지 않는다.)
```bash
# 이 머신에서 discord를 사용할 경우에만:
# 1. 플러그인 설치
claude plugin install discord@claude-plugins-official

# 2. 봇 토큰 설정
echo "DISCORD_BOT_TOKEN=여기에_봇_토큰" > ~/.claude/channels/discord/.env

# 3. 유저 ID 설정 — access.json의 allowFrom에 본인 Discord 유저 ID 추가
# 예: "allowFrom": ["123456789012345678"]
```

### Step 8: 설치 검증

설치가 올바르게 되었는지 확인한다:

```bash
# settings.json 존재 확인
[ -f ~/.claude/settings.json ] && echo "✅ settings.json" || echo "❌ settings.json"

# CLAUDE.md 존재 확인
[ -f ~/.claude/CLAUDE.md ] && echo "✅ CLAUDE.md" || echo "❌ CLAUDE.md"

# 훅 스크립트 존재 및 실행 권한 확인 (dotfiles/hooks/scripts/*.sh 전체)
# block-dangerous.sh(글로벌 차단) + voice-notify-{ack,approval,progress}.sh(음성 워크플로 자산)
for name in block-dangerous voice-notify-ack voice-notify-approval voice-notify-progress; do
  [ -x ~/.claude/hooks/scripts/$name.sh ] && echo "✅ $name.sh" || echo "❌ $name.sh"
done

# 상태줄 스크립트 확인
[ -f ~/.claude/statusline-command.sh ] && echo "✅ statusline-command.sh" || echo "❌ statusline-command.sh"

# 플러그인 메타데이터 확인
[ -f ~/.claude/plugins/installed_plugins.json ] && echo "✅ installed_plugins.json" || echo "❌ installed_plugins.json"
```

> 제외 대상(discord 등)은 install.sh가 검증하지 않는다. 머신별 관리 항목이므로 의도된 동작이다.

### Step 9: 완료 보고

설치/업데이트 결과를 요약하고, 수동 설정이 필요한 항목이 있으면 다시 한번 안내한다.

```
환경 적용이 완료되었습니다.

ℹ️ 제외 대상(sync-exclude.json): discord 등은 repo가 관리하지 않습니다.
   이 머신에서 discord를 쓰려면 직접 설치/설정하세요 (Step 7 참고).

환경을 변경한 후 repo에 반영하려면: /sync-env
```
