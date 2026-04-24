---
name: sync-dotfiles-env
description: >
  현재 머신의 dotfile 변경사항(.zshrc, .tmux.conf, Ghostty 설정,
  switch-to-abc 등)을 kywpcm/dotfiles bare repo에 커밋하고 푸시합니다.
  "dotfiles 동기화", "dotfiles 커밋", "dotfiles 푸시", "sync dotfiles",
  ".zshrc 변경사항 저장", ".tmux.conf 반영", "dotfiles status",
  "bare repo 푸시", "터미널 설정 백업", "dotfiles add",
  "Ghostty 설정 저장", "switch-to-abc 업데이트" 시 사용합니다.
  max-plugins(Claude Code 환경)용 sync-claude-env와는 다른 스킬입니다.
  shell/터미널 dotfiles 변경을 repo로 올릴 때 반드시 이 스킬을 사용하세요.
user-invocable: true
version: 0.2.0
---

# sync-dotfiles-env

현재 머신의 dotfile 변경사항을 kywpcm/dotfiles bare repo에 반영한다.
라이브 파일이 source of truth이며, repo는 이를 따라간다.

## 핵심 원칙

- bare repo는 `~/.dotfiles`, work tree는 `$HOME`이다.
- git 명령은 `dotfiles` alias (`git --git-dir=$HOME/.dotfiles --work-tree=$HOME`) 형식으로 실행한다.
- **민감 정보는 절대 커밋하지 않는다**. 토큰, API 키, 개인 식별 정보, SSH 키, `.env` 파일은 스캔으로 미리 차단한다.
- **새 파일 추적 시 신중**: `$HOME`에는 수많은 파일이 있으므로, 새로 추적할 파일은 사용자에게 반드시 확인받는다.
- 바이너리(`switch-to-abc`)는 머신별 Swift/Foundation 런타임에 묶이는 재빌드 산물이므로 기본적으로 **sync 대상이 아니다**. `.swift` 소스만 커밋한다. 자세한 절차는 Step 5 참조.
- **`--skip-worktree`가 걸린 파일은 이 머신에서 repo와 분리 관리**된다. 해당 파일의 로컬 변경은 `diff`에 뜨지 않으며 sync에 포함되지 않는다 (의도된 동작).

## Workflow

### Step 1: bare repo 상태 + skip-worktree 현황 확인

```bash
# bare repo 존재 여부
if [ ! -d "$HOME/.dotfiles" ] || [ "$(git --git-dir=$HOME/.dotfiles config core.bare 2>/dev/null)" != "true" ]; then
  echo "bare repo가 없습니다. /apply-dotfiles-env 로 먼저 설정하세요."
  exit 1
fi

# 원격 확인
git --git-dir=$HOME/.dotfiles --work-tree=$HOME remote -v
git --git-dir=$HOME/.dotfiles --work-tree=$HOME branch --show-current

# skip-worktree 현황 — 이 머신에서 로컬 관리 중인 파일은 sync에 포함되지 않음
git -C "$HOME" --git-dir=$HOME/.dotfiles --work-tree=$HOME ls-files -v | grep -E "^S " \
  && echo "(위 파일은 skip-worktree — sync에 포함되지 않음. 해제: dotfiles update-index --no-skip-worktree <경로>)" \
  || echo "skip-worktree 파일 없음"
```

사용자가 "이 skip-worktree 파일 변경을 올리고 싶다"고 요청하면, 먼저 해제 → 커밋 → 다시 `--skip-worktree` 설정의 순서를 안내한다 (Step 5의 바이너리 예외 절차와 동일한 패턴).

### Step 2: 변경 사항 조회

추적 중인 파일들의 수정 상태를 확인한다.

```bash
git --git-dir=$HOME/.dotfiles --work-tree=$HOME status
git --git-dir=$HOME/.dotfiles --work-tree=$HOME diff --stat
```

변경이 없으면 "repo와 라이브가 동일합니다"라고 알려주고 종료한다.

변경이 있으면 각 파일별로 실제 diff를 보여준다:
```bash
git --git-dir=$HOME/.dotfiles --work-tree=$HOME diff
```

### Step 3: 새 파일 추적 여부 확인 (선택적)

사용자가 특정 파일을 새로 추적해달라고 요청했거나, 대화 맥락에서 추가가 필요하다고 판단되면 진행한다. 그렇지 않으면 이 단계는 건너뛴다.

`$HOME`에는 수많은 untracked 파일이 있고 `showUntrackedFiles=no`로 숨겨져 있으므로, **사용자 명시적 요청이 있을 때만** 새 파일을 추가한다.

새로 추가할 파일이 결정되면:
1. README.md의 관리 파일 테이블에 추가 항목을 함께 업데이트한다.
2. 파일 경로를 사용자에게 재확인받고 진행한다.

### Step 4: 민감 정보 스캔

커밋 전에 변경된 파일들을 스캔한다.

```bash
# 변경 파일 목록
CHANGED=$(git --git-dir=$HOME/.dotfiles --work-tree=$HOME diff --name-only)

# 민감 키워드 스캔
for f in $CHANGED; do
  grep -nEi "token|secret|password|api[_-]?key|BEGIN (RSA|OPENSSH|EC) PRIVATE KEY|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}" "$HOME/$f" || true
done
```

매칭이 있으면 **반드시 사용자에게 경고**하고, 커밋 전 값을 환경변수/`.env`로 분리할지 확인한다.

### Step 5: 특수 파일 체크 — switch-to-abc 바이너리 정책

**원칙**: 바이너리(`switch-to-abc`)는 각 머신의 Swift/Foundation 런타임에 링크된 재빌드 산물이다. 기본적으로 **sync 대상이 아니며**, `.swift` 소스만 repo에 커밋한다. 각 머신은 `/apply-dotfiles-env` Step 9에서 자체 재빌드 후 `--skip-worktree`로 로컬 고정한다.

따라서 정상 흐름에서는 `.local/bin/switch-to-abc`가 skip-worktree이므로 `diff --name-only`에 **뜨지 않고**, 아래 불일치 경고가 발화하지 않는다 (의도된 동작).

```bash
BIN_CHANGED=$(git --git-dir=$HOME/.dotfiles --work-tree=$HOME diff --name-only -- .local/bin/switch-to-abc)
SRC_CHANGED=$(git --git-dir=$HOME/.dotfiles --work-tree=$HOME diff --name-only -- .local/bin/switch-to-abc.swift)

if [ -n "$BIN_CHANGED" ] && [ -z "$SRC_CHANGED" ]; then
  echo "⚠️  바이너리만 변경됨. 소스(.swift)도 함께 업데이트했는지 확인하세요."
fi
if [ -z "$BIN_CHANGED" ] && [ -n "$SRC_CHANGED" ]; then
  echo "⚠️  소스만 변경됨. 다른 머신들은 pull 후 swiftc로 재빌드해야 새 동작이 반영됨."
  echo "이 머신에서 로컬 테스트를 원하면: swiftc ~/.local/bin/switch-to-abc.swift -o ~/.local/bin/switch-to-abc"
fi
```

**예외 — 바이너리를 repo에 올려야 할 때** (동일 환경 머신 다수에 같은 바이너리를 공유하고 싶은 드문 경우):

```bash
# 1) 로컬에서 skip-worktree 해제
git -C "$HOME" --git-dir=$HOME/.dotfiles --work-tree=$HOME \
  update-index --no-skip-worktree ".local/bin/switch-to-abc"
# 2) 재빌드 + add + commit (이 sync 스킬의 Step 6~9 정상 흐름 탐)
# 3) push 후 다시 skip-worktree 설정하여 이 머신에서 분리 관리 복귀
git -C "$HOME" --git-dir=$HOME/.dotfiles --work-tree=$HOME \
  update-index --skip-worktree ".local/bin/switch-to-abc"
```

이 예외 경로는 다른 머신이 push된 바이너리를 **아키텍처/Swift 버전이 다른데 pull 받을 위험**이 있으므로, 실수로 재발동하지 않도록 수동 흐름으로만 둔다.

### Step 6: 사용자 확인

여기까지 발견된 내용을 정리해서 사용자에게 보여준다:

```
변경 요약:
| 파일 | 상태 | 비고 |
|------|------|------|
| .zshrc | 변경됨 | alias 1개 추가 |
| .tmux.conf | 변경됨 | theme 변경 |

경고: (민감 정보 스캔 결과, 바이너리/소스 불일치 등)

커밋 & 푸시를 진행할까요?
```

사용자가 확인하면 다음 단계로 진행한다.

### Step 7: 스테이징 & 커밋

```bash
# 변경된 추적 파일 전체 스테이징
git --git-dir=$HOME/.dotfiles --work-tree=$HOME add -u

# 새 파일이 결정되었다면 개별 add
# git --git-dir=$HOME/.dotfiles --work-tree=$HOME add ~/.config/새_파일

# 최종 확인
git --git-dir=$HOME/.dotfiles --work-tree=$HOME diff --cached --stat
```

커밋 메시지는 기존 repo 스타일을 따라 **간결하게** 작성한다. 최근 커밋을 참고:
```bash
git --git-dir=$HOME/.dotfiles --work-tree=$HOME log --oneline -5
```

형식 예 (기본):
```
update <파일>: <무엇을 바꿨는지 한 줄>

- 세부 변경 1
- 세부 변경 2
```

**Conventional Commits 스타일**을 이미 사용 중이면 그 관례를 따른다 (최근 `log -5`로 판단). 예시:
```
feat(zsh): add switch-to-abc alias
fix(tmux): correct prefix key binding
chore(shell): tweak zshrc and tmux.conf
docs(readme): document new Ghostty entry
```

어느 스타일이든 **제목 한 줄은 50자 이내**, 본문 bullet은 "무엇을" 보다 "왜"를 설명하는 게 다른 머신에서 이 커밋을 볼 때 유용하다. repo에 협업자가 없더라도, 미래의 본인이 읽는다는 생각으로 쓴다.

`git commit` 실행:
```bash
git --git-dir=$HOME/.dotfiles --work-tree=$HOME commit -m "..."
```

### Step 8: 푸시 전 원격 상태 확인

로컬 브랜치가 원격보다 뒤처져 있으면 push가 non-fast-forward로 거부된다. 다른 머신에서 이미 push했거나, GitHub 웹 UI로 repo를 수정한 경우에 발생한다. 먼저 원격 상태를 당겨와서 위치를 비교한다.

```bash
git --git-dir=$HOME/.dotfiles --work-tree=$HOME fetch origin

BR=$(git --git-dir=$HOME/.dotfiles --work-tree=$HOME branch --show-current)

# 로컬과 원격의 위치 비교
# 출력 형식: <원격 앞선 커밋 수>\t<로컬 앞선 커밋 수>
git --git-dir=$HOME/.dotfiles --work-tree=$HOME rev-list --left-right --count "origin/$BR...HEAD"
```

결과 해석:

| 원격 / 로컬 | 의미 | 대응 |
|------------|------|------|
| `0 / N` | 로컬만 앞섬 (정상 상황) | Step 9에서 그대로 push |
| `0 / 0` | 완전 동일 | Step 2로 돌아가 상태 재확인 |
| `M / 0` | 원격만 앞섬 | push할 커밋이 없음 — `/apply-dotfiles-env`로 pull 권장 |
| `M / N` | 양쪽 다 앞섬 (분기) | 사용자에게 알리고 `pull --rebase` 후 진행 |

분기 상황(`M / N`) 대응:
```bash
# 로컬 커밋을 원격 위로 재배치 — merge 커밋 없이 깔끔하게
git --git-dir=$HOME/.dotfiles --work-tree=$HOME pull --rebase origin "$BR"
```
충돌 발생 시 **자동 `rebase --abort` 금지**. 사용자에게 상황을 알리고 수동 해결을 요청한다.

### Step 9: 푸시

```bash
git --git-dir=$HOME/.dotfiles --work-tree=$HOME push origin "$BR"
```

에러별 대응:

| 에러 메시지 | 원인 | 대응 |
|------|------|------|
| `Permission denied (publickey)` | SSH 키 미설정 또는 GitHub 미등록 | SSH 키 생성 + GitHub 등록 안내, 또는 HTTPS remote 임시 변경 |
| `! [rejected] ... (non-fast-forward)` | Step 8을 건너뛴 경우 | Step 8로 돌아가 fetch/비교 후 rebase |
| `Everything up-to-date` | 실제로 올릴 커밋 없음 | Step 2로 돌아가 상태 재확인 |

**절대 하지 말 것**: `git push --force` / `--force-with-lease`는 `main` 브랜치에서는 사용하지 않는다. 원격 히스토리를 덮어써 다른 머신에서 `/apply-dotfiles-env` 시 데이터 손실이 발생할 수 있다.

### Step 10: README.md 업데이트 (새 파일 추가 시)

Step 3에서 새 파일을 추적하기로 결정했다면, `README.md`의 "관리 파일" 테이블에 새 항목을 추가하고 같이 커밋한다. 이렇게 하면 다른 머신에서 `apply-dotfiles-env`로 복원 시 새 파일이 관리 대상임을 명확히 알 수 있다.

### Step 11: 완료 보고

```
dotfiles 동기화가 완료되었습니다.

커밋: <hash> <메시지>
푸시: origin/<branch>

다른 머신에서 적용하려면: /apply-dotfiles-env
```
