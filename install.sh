#!/bin/bash
# install.sh — dotfiles를 ~/.claude/에 설치하는 스크립트
# 기존 파일은 .bak으로 백업한 후 복사한다.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DOTFILES_DIR="$SCRIPT_DIR/dotfiles"
CLAUDE_DIR="$HOME/.claude"
EXCLUDE_FILE="$DOTFILES_DIR/sync-exclude.json"  # 머신별 관리 플러그인/채널 (예: discord)

echo "=== dotfiles-claude-code installer ==="
echo "Source: $DOTFILES_DIR"
echo "Target: $CLAUDE_DIR"
echo ""

# 백업 후 복사 함수
install_file() {
  local src="$1"
  local dest="$2"

  # 대상 디렉토리 생성
  mkdir -p "$(dirname "$dest")"

  # 기존 파일이 있으면 백업
  if [ -f "$dest" ]; then
    local backup="${dest}.bak"
    echo "  [backup] $dest → $backup"
    cp "$dest" "$backup"
  fi

  cp "$src" "$dest"
  echo "  [install] $dest"
}

# 기존 파일이 없을 때만 복사 (채널 access.json 등 사용자 설정 보호)
install_file_if_missing() {
  local src="$1"
  local dest="$2"

  mkdir -p "$(dirname "$dest")"

  if [ -f "$dest" ]; then
    echo "  [skip] $dest (이미 존재)"
  else
    cp "$src" "$dest"
    echo "  [install] $dest"
  fi
}

# settings.json 전용: dotfiles/sync-fields.json에 정의된 필드만 라이브에 머지.
# 라이브의 다른 키(effortLevel, channelsEnabled 등 머신별 개인 설정)는 보존.
# 단, enabledPlugins는 sync-exclude.json의 제외 플러그인(예: discord)을
# repo가 추가/제거하지 못하도록 라이브 머신의 상태를 그대로 보존한다.
merge_settings() {
  local src="$1"
  local dest="$2"
  local fields_file="$DOTFILES_DIR/sync-fields.json"

  if [ ! -f "$fields_file" ]; then
    echo "  [error] sync-fields.json not found: $fields_file" >&2
    return 1
  fi

  mkdir -p "$(dirname "$dest")"

  if [ -f "$dest" ]; then
    local backup="${dest}.bak"
    echo "  [backup] $dest → $backup"
    cp "$dest" "$backup"
  fi

  python3 - "$src" "$dest" "$fields_file" "$EXCLUDE_FILE" <<'PY'
import json, sys, os
src_path, dest_path, fields_path, exclude_path = sys.argv[1:]

with open(fields_path) as f:
    fields = json.load(f)
with open(src_path) as f:
    src = json.load(f)
if os.path.exists(dest_path):
    with open(dest_path) as f:
        dest = json.load(f)
else:
    dest = {}

excluded = set()
if os.path.exists(exclude_path):
    with open(exclude_path) as f:
        excluded = set(json.load(f).get("plugins", []))

for key in fields:
    if key not in src:
        continue
    if key == "enabledPlugins" and excluded:
        # repo가 관리하는 플러그인만 갱신하고, 제외 플러그인은 라이브 상태를 보존
        live = dest.get("enabledPlugins", {})
        live = live if isinstance(live, dict) else {}
        merged = {k: v for k, v in src["enabledPlugins"].items() if k not in excluded}
        for pid in excluded:
            if pid in live:
                merged[pid] = live[pid]
        dest["enabledPlugins"] = merged
    else:
        dest[key] = src[key]

with open(dest_path, "w") as f:
    json.dump(dest, f, indent=2, ensure_ascii=False)
    f.write("\n")
PY
  local count=$(python3 -c "import json; print(len(json.load(open('$fields_file'))))")
  echo "  [merge] $dest ($count fields from sync-fields.json)"
}

# installed_plugins.json 전용: repo 메타데이터로 갱신하되,
# sync-exclude.json의 제외 플러그인(예: discord) 엔트리는 라이브 머신 것을 보존한다.
# (라이브 엔트리는 실제 경로, repo 엔트리는 <HOME> 플레이스홀더 — 치환은 이후 단계에서)
merge_installed_plugins() {
  local src="$1"
  local dest="$2"

  mkdir -p "$(dirname "$dest")"

  if [ -f "$dest" ]; then
    local backup="${dest}.bak"
    echo "  [backup] $dest → $backup"
    cp "$dest" "$backup"
  fi

  python3 - "$src" "$dest" "$EXCLUDE_FILE" <<'PY'
import json, sys, os
src_path, dest_path, exclude_path = sys.argv[1:]

with open(src_path) as f:
    src = json.load(f)
live = {}
if os.path.exists(dest_path):
    with open(dest_path) as f:
        live = json.load(f)

excluded = set()
if os.path.exists(exclude_path):
    with open(exclude_path) as f:
        excluded = set(json.load(f).get("plugins", []))

result = dict(src)
src_plugins = src.get("plugins", {})
live_plugins = live.get("plugins", {})
merged = {k: v for k, v in src_plugins.items() if k not in excluded}
for pid in excluded:
    if pid in live_plugins:
        merged[pid] = live_plugins[pid]
result["plugins"] = merged

with open(dest_path, "w") as f:
    json.dump(result, f, indent=2, ensure_ascii=False)
    f.write("\n")
PY
  echo "  [merge] $dest (제외 플러그인은 라이브 보존)"
}

echo "[1/4] 설정 파일 설치..."
install_file "$DOTFILES_DIR/CLAUDE.md" "$CLAUDE_DIR/CLAUDE.md"
merge_settings "$DOTFILES_DIR/settings.json" "$CLAUDE_DIR/settings.json"
install_file "$DOTFILES_DIR/statusline-command.sh" "$CLAUDE_DIR/statusline-command.sh"

echo ""
echo "[2/4] 훅 스크립트 설치..."
# dotfiles/hooks/scripts/*.sh 전체를 설치한다 (새 스크립트 추가 시 install.sh 수정 불필요).
# block-dangerous.sh(글로벌 PreToolUse)와 voice-notify-{ack,approval,progress}.sh(프로젝트별 hook 자산)가 함께 배포된다.
for script in "$DOTFILES_DIR"/hooks/scripts/*.sh; do
  [ -e "$script" ] || continue
  name="$(basename "$script")"
  install_file "$script" "$CLAUDE_DIR/hooks/scripts/$name"
  chmod +x "$CLAUDE_DIR/hooks/scripts/$name"
done

echo ""
echo "[3/4] 플러그인 메타데이터 설치 (참조용)..."
# installed_plugins.json: 제외 플러그인(discord 등)은 라이브 머신 것을 보존하며 머지
merge_installed_plugins "$DOTFILES_DIR/meta/installed_plugins.json" "$CLAUDE_DIR/plugins/installed_plugins.json"
install_file "$DOTFILES_DIR/meta/known_marketplaces.json" "$CLAUDE_DIR/plugins/known_marketplaces.json"

echo ""
echo "[4/4] 경로 치환..."
# installed_plugins.json과 known_marketplaces.json의 <HOME> 플레이스홀더를 실제 경로로 변경
sed -i '' "s|<HOME>|$HOME|g" "$CLAUDE_DIR/plugins/installed_plugins.json" 2>/dev/null || \
sed -i "s|<HOME>|$HOME|g" "$CLAUDE_DIR/plugins/installed_plugins.json"
sed -i '' "s|<HOME>|$HOME|g" "$CLAUDE_DIR/plugins/known_marketplaces.json" 2>/dev/null || \
sed -i "s|<HOME>|$HOME|g" "$CLAUDE_DIR/plugins/known_marketplaces.json"

echo ""
echo "=== 설치 완료! ==="
echo ""
echo "⚠️  다음 항목은 수동 설정이 필요합니다:"
echo "  1. settings.json의 enabledPlugins: 실제 설치된 플러그인에 맞게 조정"
echo "  2. (선택) terminal-notifier: 권한 승인/작업 완료 알림용. brew install terminal-notifier"
echo ""
echo "ℹ️  sync-exclude.json에 명시된 플러그인/채널(예: discord)은 이 스크립트가 건드리지 않습니다."
echo "   머신별로 직접 설치/설정하세요 (봇 토큰, access.json allowFrom 등)."
echo ""
echo "플러그인이 아직 설치되지 않았다면:"
echo "  claude plugin marketplace add --source github:kywpcm/max-plugins"
echo "  claude plugin install dotfiles-claude-code@max-plugins"
