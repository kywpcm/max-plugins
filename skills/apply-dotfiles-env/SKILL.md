---
name: apply-dotfiles-env
description: >
  kywpcm/dotfiles bare repo를 사용하여 현재 머신에 개인 dotfiles
  (.zshrc, .tmux.conf, Ghostty 설정, switch-to-abc 등)를 적용합니다.
  새 머신에서 초기 복원하거나, 기존 머신의 dotfiles를 최신 repo 상태로
  pull 받을 때 사용합니다.
  "dotfiles 적용", "dotfiles 복원", "dotfiles 체크아웃", "apply dotfiles",
  "새 머신 dotfiles 설정", "dotfiles pull", "dotfiles checkout",
  ".zshrc 복원", ".tmux.conf 복원", "Ghostty 설정 복원",
  "bare repo 클론", "switch-to-abc 설치", "터미널 설정 복원" 시 사용합니다.
  max-plugins(Claude Code 환경)용 apply-claude-env와는 다른 스킬입니다.
  shell/터미널 dotfiles를 다룰 때 반드시 이 스킬을 사용하세요.
user-invocable: true
version: 0.1.0
---

# apply-dotfiles-env

kywpcm/dotfiles bare repo에서 개인 dotfiles를 현재 머신에 적용한다.
초기 복원(신규 머신)과 업데이트(기존 머신 pull) 두 모드를 모두 지원한다.

## 핵심 원칙

- bare repo는 `~/.dotfiles`, work tree는 `$HOME`이다.
- git 명령은 `dotfiles` alias 또는 `git --git-dir=$HOME/.dotfiles --work-tree=$HOME` 풀 형식으로 실행한다.
- 초기 체크아웃 시 $HOME에 이미 존재하는 파일은 **백업 후** 덮어쓴다. 절대 덮어쓰기 전에 원본을 날려서는 안 된다.
- `git clone` 명령은 사용자가 직접 터미널에서 실행하도록 안내한다 (SSH key prompt 가능성 때문).
- 바이너리(`switch-to-abc`)는 repo에 포함되어 있지만, 아키텍처가 다른 머신이면 `.swift` 소스에서 재빌드한다.

## Workflow

### Step 1: 현재 상태 진단

어느 모드로 진행할지 먼저 판단한다.

```bash
# bare repo가 이미 클론되어 있는지 확인
[ -d "$HOME/.dotfiles" ] && [ "$(git --git-dir=$HOME/.dotfiles config core.bare 2>/dev/null)" = "true" ] \
  && echo "bare_repo_exists" || echo "bare_repo_missing"

# 체크아웃된 파일 존재 여부
for f in ~/.zshrc ~/.tmux.conf "$HOME/Library/Application Support/com.mitchellh.ghostty/config.ghostty"; do
  [ -e "$f" ] && echo "exists: $f" || echo "missing: $f"
done

# dotfiles alias 정의 여부
grep -q "alias dotfiles=" ~/.zshrc 2>/dev/null && echo "alias_present" || echo "alias_missing"
```

결과로 모드를 결정한다:
- **초기 복원**: bare repo가 없고 체크아웃도 없음 → Step 2부터
- **업데이트**: bare repo가 있고 체크아웃도 있음 → Step 7(업데이트 모드)부터

### Step 2: 사전 요구사항 확인 (초기 복원 시)

```bash
git --version        # git 필수
tmux -V              # .tmux.conf 사용 시 tmux 필요
swiftc --version 2>/dev/null || echo "swift 없음 — switch-to-abc 바이너리가 작동하지 않으면 재빌드 불가"
```

미설치 항목이 있으면 설치 안내:
- macOS: `xcode-select --install` (swiftc, git 포함), `brew install tmux`
- 다른 OS: 해당 패키지 매니저로 git, tmux 설치

### Step 3: bare repo 클론 (초기 복원 시)

SSH 인증이 필요하므로 사용자가 직접 실행하도록 안내한다.

```
아래 명령어를 터미널에서 직접 실행해 주세요:

git clone --bare git@github.com:kywpcm/dotfiles.git ~/.dotfiles
```

SSH 키가 없으면 HTTPS로 대안 제시:
```bash
git clone --bare https://github.com/kywpcm/dotfiles.git ~/.dotfiles
```

완료되면 다음 단계로 진행한다.

### Step 4: 기존 파일 백업 후 체크아웃

체크아웃 시도하고 충돌이 있으면 백업한 뒤 재시도한다.

```bash
git --git-dir=$HOME/.dotfiles --work-tree=$HOME checkout 2>/tmp/dotfiles-checkout.err
if [ $? -ne 0 ]; then
  mkdir -p ~/.dotfiles-backup
  grep -E "^\s+\S" /tmp/dotfiles-checkout.err | awk '{print $1}' | while read f; do
    # 디렉토리 경로 유지하면서 백업
    mkdir -p "$HOME/.dotfiles-backup/$(dirname "$f")"
    mv "$HOME/$f" "$HOME/.dotfiles-backup/$f"
  done
  git --git-dir=$HOME/.dotfiles --work-tree=$HOME checkout
fi
```

백업이 발생했으면 사용자에게 경로(`~/.dotfiles-backup/`)를 알려준다.

### Step 5: local git 설정

$HOME의 수많은 untracked 파일이 `status`에 표시되지 않도록 한다.

```bash
git --git-dir=$HOME/.dotfiles --work-tree=$HOME config --local status.showUntrackedFiles no
```

### Step 6: alias 확인

체크아웃된 `.zshrc`에 이미 `alias dotfiles='git --git-dir=$HOME/.dotfiles --work-tree=$HOME'`가 포함되어 있다. 새 셸을 열면 자동 적용된다.

만약 `.zshrc`에 alias가 없다면(다른 셸 사용 등) 직접 추가를 안내한다:
```bash
echo "alias dotfiles='git --git-dir=\$HOME/.dotfiles --work-tree=\$HOME'" >> ~/.zshrc
```

### Step 7: 업데이트 모드 (기존 머신에서 최신 상태로)

기존 머신에서 repo의 최신 변경사항을 받아오는 경우는 여기서 시작한다.

```bash
# 커밋 안 된 로컬 변경이 있는지 먼저 확인
git --git-dir=$HOME/.dotfiles --work-tree=$HOME status

# 변경이 있으면 사용자 확인 후 stash 또는 sync-dotfiles-env 먼저 안내
# 깨끗하면 pull
git --git-dir=$HOME/.dotfiles --work-tree=$HOME pull origin main
```

로컬 수정사항이 있으면 자동으로 덮어쓰지 말고, 사용자에게 먼저 `/sync-dotfiles-env`로 커밋할지 물어본다.

### Step 8: tmux 플러그인 매니저(TPM) 설치 (필요 시)

`.tmux.conf`가 TPM을 사용하므로 TPM이 없으면 설치한다.

```bash
if [ ! -d ~/.tmux/plugins/tpm ]; then
  git clone https://github.com/tmux-plugins/tpm ~/.tmux/plugins/tpm
fi
```

그 후 사용자에게 안내:
```
tmux를 실행한 뒤 Prefix + I 를 눌러 플러그인을 설치하세요.
(Prefix는 보통 Ctrl+b 또는 .tmux.conf에서 설정한 키)
```

### Step 9: switch-to-abc 바이너리 확인

repo에 포함된 바이너리(`~/.local/bin/switch-to-abc`)가 현재 머신에서 동작하는지 확인한다. macOS는 **(1) 아키텍처 불일치, (2) Gatekeeper quarantine, (3) 실행 권한**이라는 세 가지 이유로 바이너리 실행을 거부할 수 있다. 증상별로 대응 경로가 다르니 에러를 먼저 정확히 식별한다.

```bash
# 실행 권한 부여 (먼저 시도)
chmod +x ~/.local/bin/switch-to-abc 2>/dev/null

# 테스트 실행 — stderr 캡처해서 증상 판별
~/.local/bin/switch-to-abc --help 2>/tmp/switch-to-abc.err
BIN_RC=$?
echo "---stderr---"
cat /tmp/switch-to-abc.err
```

증상별 분기:

| 증상 (stderr 또는 exit code) | 원인 | 대응 경로 |
|------|------|------|
| 정상 출력 (RC=0) | — | 넘어감 |
| `bad CPU type in executable` | 아키텍처 불일치 (Intel 바이너리 ↔ Apple Silicon) | **(A) swiftc 재빌드** 또는 (B) Rosetta |
| `cannot be opened because the developer cannot be verified`, `Killed: 9` | Gatekeeper quarantine 속성이 붙음 | **(C) xattr 해제** |
| `Permission denied` | 실행 권한 누락 | `chmod +x` 재시도 — 실패 시 파일시스템/ACL 점검 |
| 바이너리 자체가 없음 | git에서 누락 | `git --git-dir=$HOME/.dotfiles --work-tree=$HOME ls-tree -r HEAD --name-only \| grep switch-to-abc` 로 추적 확인 |

**(A) swiftc 재빌드** (권장 — 소스가 repo에 함께 있으므로 깨끗한 해결):
```bash
if command -v swiftc >/dev/null 2>&1; then
  swiftc ~/.local/bin/switch-to-abc.swift -o ~/.local/bin/switch-to-abc
  chmod +x ~/.local/bin/switch-to-abc
  ~/.local/bin/switch-to-abc --help 2>&1 | head -3
else
  echo "swiftc 미설치 — Xcode Command Line Tools 설치 필요: xcode-select --install"
fi
```

**(B) Rosetta** (swiftc 없이 Intel 바이너리를 그대로 쓰는 드문 경우 — 관리자 권한 프롬프트 발생):
사용자가 터미널에서 직접 실행하도록 안내:
```
softwareupdate --install-rosetta --agree-to-license
```

**(C) Gatekeeper quarantine 해제** (다운로드받은 바이너리가 git clone 후에도 속성이 남는 경우):
```bash
xattr -d com.apple.quarantine ~/.local/bin/switch-to-abc 2>/dev/null
# 속성이 있는지 먼저 확인하려면:
xattr ~/.local/bin/switch-to-abc
```

**PATH 점검**:
```bash
echo ":$PATH:" | grep -q ":$HOME/.local/bin:" && echo "path_ok" || echo "path_missing"
```
`path_missing`이면 체크아웃된 `.zshrc`에 `PATH="$HOME/.local/bin:$PATH"` 류의 추가가 있는지 재확인하고, 없으면 사용자에게 알린다.

### Step 10: 설치 검증

```bash
# 체크아웃된 파일 확인
for f in ~/.zshrc ~/.tmux.conf "$HOME/Library/Application Support/com.mitchellh.ghostty/config.ghostty" ~/.local/bin/switch-to-abc ~/.local/bin/switch-to-abc.swift; do
  [ -e "$f" ] && echo "✅ $f" || echo "❌ $f"
done

# alias 등록 확인
grep -q "alias dotfiles=" ~/.zshrc && echo "✅ dotfiles alias" || echo "❌ dotfiles alias"

# bare repo 상태
git --git-dir=$HOME/.dotfiles --work-tree=$HOME log --oneline -1
```

### Step 11: 완료 보고

변경 내용과 남은 수동 작업을 요약한다.

```
dotfiles 적용이 완료되었습니다.

수동으로 처리할 항목:
  - 새 셸을 열거나 `source ~/.zshrc` 실행
  - tmux 실행 후 Prefix + I 로 플러그인 설치
  - (백업 발생 시) ~/.dotfiles-backup/ 에서 필요한 설정을 수동 병합

dotfiles를 수정한 뒤 repo에 반영하려면: /sync-dotfiles-env
```
