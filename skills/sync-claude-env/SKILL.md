---
name: sync-claude-env
description: >
  현재 라이브 Claude Code 환경(~/.claude/)의 변경사항을 max-plugins repo에 동기화합니다.
  settings.json, CLAUDE.md, hook scripts, 플러그인 메타데이터, 채널 설정 등을
  비교하고 repo를 최신 환경에 맞게 업데이트합니다.
  "환경 동기화", "sync env", "dotfiles 동기화", "플러그인 설정 동기화",
  "env sync", "설정 동기화", "환경 반영", "dotfiles sync", "맥스 플러그인 동기화",
  "max-plugins 업데이트", "설정 업데이트", "환경 업데이트" 시 사용합니다.
  새 플러그인 추가, 설정 변경, 새 채널(Discord/Telegram 등) 추가 후에도 사용하세요.
user-invocable: true
version: 0.1.0
---

# sync-env

현재 머신의 라이브 Claude Code 환경(`~/.claude/`)과 max-plugins repo를 비교하고, 변경사항을 repo에 반영하여 다른 머신에서도 동일 환경을 재현할 수 있도록 한다.

## 핵심 원칙

- 라이브 환경이 source of truth이다. repo는 라이브를 따라간다.
- 민감 정보(봇 토큰, 유저 ID)는 절대 커밋하지 않는다.
- `installed_plugins.json`의 경로는 `<HOME>` 플레이스홀더로 변환한다.
- 채널 access.json은 빈 allowlist 템플릿만 repo에 저장한다.

## Workflow

### Step 1: max-plugins repo 위치 확인

```bash
# 일반적인 위치 확인
find ~/workspace ~/projects ~ -maxdepth 3 -type d -name "max-plugins" 2>/dev/null | head -1
```

repo를 찾지 못하면 사용자에게 경로를 물어본다. 찾으면 `REPO_DIR` 변수에 저장한다.

### Step 2: 파일별 비교

아래 파일들을 라이브 환경과 repo 사이에서 `diff`로 비교한다:

| 라이브 경로 | repo 경로 |
|------------|-----------|
| `~/.claude/settings.json` | `$REPO_DIR/dotfiles/settings.json` |
| `~/.claude/CLAUDE.md` | `$REPO_DIR/dotfiles/CLAUDE.md` |
| `~/.claude/statusline-command.sh` | `$REPO_DIR/dotfiles/statusline-command.sh` |
| `~/.claude/hooks/scripts/block-dangerous.sh` | `$REPO_DIR/dotfiles/hooks/scripts/block-dangerous.sh` |
| `~/.claude/hooks/scripts/save-conv-before-commit.sh` | `$REPO_DIR/dotfiles/hooks/scripts/save-conv-before-commit.sh` |

```bash
diff ~/.claude/settings.json "$REPO_DIR/dotfiles/settings.json"
diff ~/.claude/CLAUDE.md "$REPO_DIR/dotfiles/CLAUDE.md"
# ... 각 파일에 대해 반복
```

### Step 3: 플러그인 메타데이터 비교

메타데이터 파일은 경로에 실제 HOME 경로가 들어 있으므로, 비교 전에 `<HOME>` 플레이스홀더로 변환해서 비교해야 한다.

```bash
# 라이브 installed_plugins.json에서 HOME 경로를 <HOME>으로 치환 후 비교
sed "s|$HOME|<HOME>|g" ~/.claude/plugins/installed_plugins.json > /tmp/live_installed_plugins.json
diff /tmp/live_installed_plugins.json "$REPO_DIR/dotfiles/meta/installed_plugins.json"

# known_marketplaces.json도 동일하게
sed "s|$HOME|<HOME>|g" ~/.claude/plugins/known_marketplaces.json > /tmp/live_known_marketplaces.json
diff /tmp/live_known_marketplaces.json "$REPO_DIR/dotfiles/meta/known_marketplaces.json"
```

### Step 4: 채널 설정 비교

라이브 환경의 채널 디렉토리를 확인하고, repo에 없는 새 채널이 있는지 감지한다.

```bash
# 라이브 채널 목록
ls ~/.claude/channels/ 2>/dev/null

# repo 채널 템플릿 목록 (파일명에서 추출)
ls "$REPO_DIR/dotfiles/meta/"*-access.json 2>/dev/null
```

**새 채널 감지 규칙:**
- 라이브에 `~/.claude/channels/{channel}/access.json`이 있지만 repo에 `dotfiles/meta/{channel}-access.json`이 없으면 → 새 채널

### Step 5: 차이점 요약 및 사용자 확인

발견된 모든 차이점을 표로 정리하여 사용자에게 보여준다:

```
| 파일 | 상태 | 설명 |
|------|------|------|
| settings.json | 변경됨 | telegram 플러그인 추가, 훅 구조 변경 |
| installed_plugins.json | 변경됨 | telegram 엔트리 추가 |
| CLAUDE.md | 동일 | - |
```

차이가 없으면 "라이브 환경과 repo가 동일합니다"라고 알려주고 종료한다.

### Step 6: repo 파일 업데이트

사용자가 확인하면, 변경된 파일들을 업데이트한다.

**일반 설정 파일** (settings.json, CLAUDE.md, statusline-command.sh, hook scripts):
- 라이브 파일을 그대로 repo에 복사한다.

**플러그인 메타데이터** (installed_plugins.json, known_marketplaces.json):
- 라이브 파일에서 `$HOME` 경로를 `<HOME>`으로 치환하여 저장한다.
```bash
sed "s|$HOME|<HOME>|g" ~/.claude/plugins/installed_plugins.json > "$REPO_DIR/dotfiles/meta/installed_plugins.json"
sed "s|$HOME|<HOME>|g" ~/.claude/plugins/known_marketplaces.json > "$REPO_DIR/dotfiles/meta/known_marketplaces.json"
```

### Step 7: 새 채널 처리

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
