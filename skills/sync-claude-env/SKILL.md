---
name: sync-claude-env
description: >
  현재 라이브 Claude Code 환경(~/.claude/)의 변경사항을 max-plugins repo에 동기화합니다.
  settings.json, CLAUDE.md, hook scripts, 플러그인 메타데이터, 채널 설정 등을
  비교하고 repo를 최신 환경에 맞게 업데이트합니다.
  "claude 환경 동기화", "sync claude env", "env sync",
  "플러그인 설정 동기화", "settings.json 동기화", "CLAUDE.md 반영",
  "훅 동기화", "맥스 플러그인 동기화", "max-plugins 업데이트",
  "claude 설정 업데이트", "claude 환경 반영", "claude 환경 업데이트" 시 사용합니다.
  shell/터미널 dotfiles(.zshrc/.tmux.conf 등)가 아닌 Claude Code 환경 전용입니다.
  순수 dotfiles를 repo로 올리려면 sync-dotfiles-env를 사용하세요.
  새 플러그인 추가, 설정 변경, 새 채널(Discord 등) 추가 후에도 사용하세요.
user-invocable: true
version: 0.1.0
---

# sync-env

현재 머신의 라이브 Claude Code 환경(`~/.claude/`)과 max-plugins repo를 비교하고, 변경사항을 repo에 반영하여 다른 머신에서도 동일 환경을 재현할 수 있도록 한다.

## 핵심 원칙

- 라이브 환경이 source of truth이다. repo는 라이브를 따라간다.
- 민감 정보(봇 토큰, 유저 ID)는 절대 커밋하지 않는다.
- **`installed_plugins.json`은 sync 대상이 아니다.** Claude Code가 `claude plugin install/update` 시 cache 실물 기준으로 자동 생성/갱신하는 파생 상태(derived state)이며, 머신마다 cache에 있는 버전·경로가 달라 한 머신의 스냅샷을 repo로 공유하면 다른 머신에서 존재하지 않는 cache 경로를 가리켜 깨진다. repo에서 관리하는 플러그인 메타는 `known_marketplaces.json`뿐이며, 그 경로만 `<HOME>` 플레이스홀더로 변환한다.
- 채널 access.json은 빈 allowlist 템플릿만 repo에 저장한다.
- **settings.json은 `dotfiles/sync-fields.json`에 나열된 필드만 동기화**한다 (현재 5개: `permissions`, `hooks`, `statusLine`, `enabledPlugins`, `extraKnownMarketplaces`). 그 외 키(`effortLevel`, `channelsEnabled`, `skipDangerousModePermissionPrompt`, `skipAutoPermissionPrompt` 등)는 머신별 개인 선호로 간주하고 sync/apply 어느 방향에서도 건드리지 않는다. 동기화 대상을 늘리거나 줄이려면 `dotfiles/sync-fields.json` 한 곳만 수정하면 양방향 모두 반영된다.
- **`dotfiles/sync-exclude.json`에 나열된 플러그인/채널은 sync/apply 양방향에서 제외**한다 (현재 `discord@claude-plugins-official` 플러그인, `discord` 채널). 제외 플러그인은 repo의 `enabledPlugins`에 **절대 기록하지 않고**, 제외 채널은 "새 채널 감지"에서 건너뛴다. discord 같은 항목은 각 머신에서 따로 관리된다. 제외 대상을 바꾸려면 `dotfiles/sync-exclude.json` 한 곳만 수정하면 양방향 모두 반영된다.

## Workflow

### Step 1: max-plugins repo 위치 확인

```bash
# 일반적인 위치 확인
find ~/workspace ~/projects ~ -maxdepth 3 -type d -name "max-plugins" 2>/dev/null | head -1
```

repo를 찾지 못하면 사용자에게 경로를 물어본다. 찾으면 `REPO_DIR` 변수에 저장한다.

**비교·커밋 전에 반드시 origin/master를 pull한다.** sync는 repo에 **쓰기**를 하므로, 로컬이 원격보다 뒤처진 상태에서 커밋하면 다른 머신의 최신 변경 위에 stale base로 커밋해 push 충돌·분기가 생긴다. 작업 시작 전 최신화로 이를 막는다.

```bash
if [ -n "$REPO_DIR" ] && [ -d "$REPO_DIR/.git" ]; then
  cd "$REPO_DIR" && git pull --ff-only origin master
fi
```

> `--ff-only`로 pull해 의도치 않은 머지 커밋을 막는다. fast-forward가 불가능하면(로컬에 미푸시 커밋 존재) 사용자에게 알리고, 먼저 정리(rebase/push)할지 확인한 뒤 진행한다.

### Step 2: 파일별 비교

아래 파일들을 라이브 환경과 repo 사이에서 비교한다:

| 라이브 경로 | repo 경로 | 비교 방식 |
|------------|-----------|---------|
| `~/.claude/settings.json` | `$REPO_DIR/dotfiles/settings.json` | **5개 필드만** 추출 후 diff |
| `~/.claude/CLAUDE.md` | `$REPO_DIR/dotfiles/CLAUDE.md` | 전체 diff |
| `~/.claude/statusline-command.sh` | `$REPO_DIR/dotfiles/statusline-command.sh` | 전체 diff |
| `~/.claude/hooks/scripts/*.sh` | `$REPO_DIR/dotfiles/hooks/scripts/*.sh` | **모든 hook 스크립트** 전체 diff |

> hook 스크립트는 특정 파일을 나열하지 않고 `~/.claude/hooks/scripts/*.sh` 전체를 비교한다. 현재 `block-dangerous.sh`(글로벌 PreToolUse 차단)와 `voice-notify-{ack,approval,progress}.sh`(project-discord-setup 음성 워크플로 자산)가 여기에 해당한다. 새 스크립트가 라이브에만 있으면 "추가됨"으로 잡고 repo에 복사한다.

settings.json은 `dotfiles/sync-fields.json`에 나열된 필드만 떼어내서 비교한다 (그 외 키 차이는 의도된 머신별 차이이므로 노이즈로 본다). 라이브 추출 시 `sync-exclude.json`의 제외 플러그인은 `enabledPlugins`에서 걸러내, repo가 discord 같은 항목을 절대 흡수하지 않도록 한다:

```bash
python3 - "$REPO_DIR" <<'PY' > /tmp/live_settings_subset.json
import json, sys, os
repo_dir = sys.argv[1]
fields = json.load(open(f"{repo_dir}/dotfiles/sync-fields.json"))
excluded = set(json.load(open(f"{repo_dir}/dotfiles/sync-exclude.json")).get("plugins", []))
src = json.load(open(os.path.expanduser("~/.claude/settings.json")))
subset = {k: src[k] for k in fields if k in src}
if "enabledPlugins" in subset:
    subset["enabledPlugins"] = {k: v for k, v in subset["enabledPlugins"].items() if k not in excluded}
print(json.dumps(subset, indent=2, ensure_ascii=False))
PY

python3 - "$REPO_DIR" <<'PY' > /tmp/repo_settings_subset.json
import json, sys
repo_dir = sys.argv[1]
fields = json.load(open(f"{repo_dir}/dotfiles/sync-fields.json"))
src = json.load(open(f"{repo_dir}/dotfiles/settings.json"))
print(json.dumps({k: src[k] for k in fields if k in src}, indent=2, ensure_ascii=False))
PY

diff /tmp/live_settings_subset.json /tmp/repo_settings_subset.json
```

나머지 파일은 전체 diff:

```bash
diff ~/.claude/CLAUDE.md "$REPO_DIR/dotfiles/CLAUDE.md"
diff ~/.claude/statusline-command.sh "$REPO_DIR/dotfiles/statusline-command.sh"

# hook 스크립트: 라이브의 *.sh 전체를 순회하며 비교 (repo에 없으면 "추가됨")
for live in ~/.claude/hooks/scripts/*.sh; do
  name="$(basename "$live")"
  repo_file="$REPO_DIR/dotfiles/hooks/scripts/$name"
  if [ ! -f "$repo_file" ]; then
    echo "[추가됨] $name — repo에 없음, 복사 필요"
  else
    diff "$live" "$repo_file" && echo "[동일] $name"
  fi
done
```

### Step 3: 마켓플레이스 메타데이터 비교

> `installed_plugins.json`은 **비교·동기화하지 않는다** (파생 상태 — 핵심 원칙 참고). repo에서 관리하는 플러그인 메타는 `known_marketplaces.json`뿐이다.

`known_marketplaces.json`은 경로에 실제 HOME 경로가 들어 있으므로, 비교 전에 `<HOME>` 플레이스홀더로 변환해서 비교한다.

```bash
# known_marketplaces.json: HOME 경로를 <HOME>으로 치환 후 비교 (마켓플레이스는 제외 대상 아님)
sed "s|$HOME|<HOME>|g" ~/.claude/plugins/known_marketplaces.json > /tmp/live_known_marketplaces.json
diff /tmp/live_known_marketplaces.json "$REPO_DIR/dotfiles/meta/known_marketplaces.json"
```

> `lastUpdated` 타임스탬프만 다른 경우가 잦다 — 의미 있는 변경(마켓플레이스 추가/삭제/소스 변경)이 없으면 동기화하지 않아도 된다.

### Step 4: 채널 설정 비교

라이브 환경의 채널 디렉토리를 확인하고, repo에 없는 새 채널이 있는지 감지한다.

```bash
# 라이브 채널 목록
ls ~/.claude/channels/ 2>/dev/null

# repo 채널 템플릿 목록 (파일명에서 추출)
ls "$REPO_DIR/dotfiles/meta/"*-access.json 2>/dev/null

# sync-exclude.json의 제외 채널 목록 (감지에서 건너뛸 대상)
python3 -c "import json; print(' '.join(json.load(open('$REPO_DIR/dotfiles/sync-exclude.json')).get('channels', [])))"
```

**새 채널 감지 규칙:**
- 라이브에 `~/.claude/channels/{channel}/access.json`이 있지만 repo에 `dotfiles/meta/{channel}-access.json`이 없으면 → 새 채널
- **단, `sync-exclude.json`의 `channels`에 있는 채널(현재 `discord`)은 제외** — 각 머신에서 따로 관리되므로 "새 채널"로 잡지 않고, repo에 템플릿을 만들지도, install.sh에 스텝을 추가하지도 않는다.

### Step 5: 차이점 요약 및 사용자 확인

발견된 모든 차이점을 표로 정리하여 사용자에게 보여준다:

```
| 파일 | 상태 | 설명 |
|------|------|------|
| settings.json | 변경됨 | 새 플러그인 추가, 훅 구조 변경 |
| hooks/scripts/*.sh | 변경됨 | 새 hook 스크립트 추가 |
| CLAUDE.md | 동일 | - |
```

차이가 없으면 "라이브 환경과 repo가 동일합니다"라고 알려주고 종료한다.

### Step 6: repo 파일 업데이트

사용자가 확인하면, 변경된 파일들을 업데이트한다.

**settings.json (`sync-fields.json` 정의 필드만 머지, 제외 플러그인은 드롭)**:
라이브의 동기화 대상 필드만 repo로 옮기고, repo의 다른 키는 절대 건드리지 않는다. `enabledPlugins`는 `sync-exclude.json`의 제외 플러그인을 빼고 기록해, repo가 discord 같은 항목을 절대 담지 않게 한다. install.sh의 `merge_settings`와 동일한 머지 로직을 sync 방향으로 적용.

```bash
python3 - "$HOME/.claude/settings.json" "$REPO_DIR/dotfiles/settings.json" "$REPO_DIR/dotfiles/sync-fields.json" "$REPO_DIR/dotfiles/sync-exclude.json" <<'PY'
import json, sys, os
src_path, dest_path, fields_path, exclude_path = sys.argv[1:]

fields = json.load(open(fields_path))
excluded = set(json.load(open(exclude_path)).get("plugins", []))
src = json.load(open(src_path))
dest = json.load(open(dest_path)) if os.path.exists(dest_path) else {}

for key in fields:
    if key not in src:
        continue
    if key == "enabledPlugins":
        dest["enabledPlugins"] = {k: v for k, v in src["enabledPlugins"].items() if k not in excluded}
    else:
        dest[key] = src[key]

with open(dest_path, "w") as f:
    json.dump(dest, f, indent=2, ensure_ascii=False)
    f.write("\n")
PY
```

**일반 설정 파일** (CLAUDE.md, statusline-command.sh, hook scripts):
- 라이브 파일을 그대로 repo에 복사한다.

**마켓플레이스 메타데이터** (known_marketplaces.json만):
- `$HOME` 경로를 `<HOME>`으로 치환하여 저장한다. (`installed_plugins.json`은 동기화하지 않는다 — 파생 상태.)
```bash
sed "s|$HOME|<HOME>|g" ~/.claude/plugins/known_marketplaces.json > "$REPO_DIR/dotfiles/meta/known_marketplaces.json"
```

### Step 7: 새 채널 처리

> `sync-exclude.json`의 `channels`에 있는 채널(현재 `discord`)은 Step 4에서 이미 걸러졌으므로 여기 도달하지 않는다. 아래는 그 외 새 채널에만 적용한다.

새 채널이 감지되었으면:

1. **access.json 템플릿 생성**: 빈 allowlist 템플릿을 `dotfiles/meta/{channel}-access.json`에 생성
```json
{
  "dmPolicy": "allowlist",
  "allowFrom": [],
  "groups": {},
  "pending": {}
}
```

2. **install.sh 업데이트**: 새 채널 설치 스텝을 추가
   - 총 스텝 수를 +1 증가시킨다
   - 기존 채널 스텝 뒤에 새 스텝을 추가한다
   - `install_file_if_missing` 함수를 사용하여 기존 설정을 보호한다
   - 경로 치환 스텝의 번호를 업데이트한다

3. **README.md 업데이트**: "수동 설정" 섹션에 새 채널의 봇 토큰과 유저 ID 안내를 추가

### Step 8: 플러그인 버전 bump

repo에 변경사항이 있으면 `/plugin update`가 다른 머신에 반영되도록 `plugin.json`과 `marketplace.json`의 `version`을 올린다.

**왜 필요한가**: Claude Code는 `plugin.json`의 `version` 필드로 업데이트 여부를 판단한다. git 커밋만 있고 version이 그대로면 "already at latest"로 인식되어 다른 머신에 반영되지 않는다.

**semver 판단 규칙** (`MAJOR.MINOR.PATCH`):

| 레벨 | 언제 올리나 | 예시 |
|------|-------------|------|
| **patch** (`X.Y.Z → X.Y.(Z+1)`) | `dotfiles/` 설정·훅·스크립트만 변경 | settings.json 훅 수정, statusline 개선 |
| **minor** (`X.Y.Z → X.(Y+1).0`) | `skills/` 또는 `commands/`의 추가·삭제·의미있는 변경, 새 채널, 새 기능 | 새 skill 추가, skill workflow 큰 변경 |
| **major** (`X.Y.Z → (X+1).0.0`) | breaking change | skill 이름·동작 변경, install.sh 파괴적 변경 |

판단이 애매하면 사용자에게 확인한다.

**bump 대상 필드** (두 파일 모두 동일 버전으로):
- `.claude-plugin/plugin.json` → `version`
- `.claude-plugin/marketplace.json` → `plugins[0].version`

> `marketplace.json`의 최상위 `metadata.version`은 **마켓플레이스 스키마 버전**이다. 마켓플레이스 구조 자체가 바뀔 때만 올리고, 플러그인 변경에는 건드리지 않는다.

**절차**:

```bash
# 1. 현재 버전 확인
CURRENT=$(python3 -c "import json; print(json.load(open('$REPO_DIR/.claude-plugin/plugin.json'))['version'])")
echo "Current: $CURRENT"
```

```bash
# 2. 새 버전 결정 후 두 파일 동시 업데이트 (예: 1.1.0 → 1.1.1)
NEW_VERSION="1.1.1"
python3 <<PY
import json
for path, key in [
    ('$REPO_DIR/.claude-plugin/plugin.json', ['version']),
    ('$REPO_DIR/.claude-plugin/marketplace.json', ['plugins', 0, 'version']),
]:
    d = json.load(open(path))
    ref = d
    for k in key[:-1]: ref = ref[k]
    ref[key[-1]] = '$NEW_VERSION'
    json.dump(d, open(path, 'w'), indent=2, ensure_ascii=False)
    print(f"updated {path}")
PY
```

변경사항이 전혀 없으면 bump는 생략한다.

### Step 9: 보안 점검

커밋 전 보안 스캔을 수행한다:

```bash
# 하드코딩된 시크릿 검색
grep -r "token\|secret\|password\|api_key\|BOT_TOKEN" --include='*.json' --include='*.sh' --include='*.md' "$REPO_DIR/dotfiles/"

# 유저 ID 노출 확인 (allowFrom에 실제 ID가 들어있는지)
grep -r "allowFrom.*[0-9]\{5,\}" "$REPO_DIR/dotfiles/"

# .env 파일이 추적되고 있는지
git -C "$REPO_DIR" ls-files '*.env' '.env'

# .gitignore 확인
cat "$REPO_DIR/.gitignore"
```

문제가 발견되면 사용자에게 경고하고 수정 방법을 안내한다.

### Step 10: 변경사항 커밋 및 푸시

```bash
cd "$REPO_DIR"
git add -A
git diff --cached --stat  # 변경 사항 최종 확인
```

커밋 메시지는 변경 내용을 요약하되, 아래 형식을 따른다:
```
sync: {변경 요약}

- {변경 항목 1}
- {변경 항목 2}
...
```

사용자 확인 후 커밋하고 푸시한다.

### Step 11: 완료 보고

변경 사항 요약과 함께, 다른 머신에서 적용하는 방법을 안내한다:
```
다른 머신에서 적용하려면: /apply-env
```
