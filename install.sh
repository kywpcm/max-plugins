#!/bin/bash
# install.sh — dotfiles를 ~/.claude/에 설치하는 스크립트
# 기존 파일은 .bak으로 백업한 후 복사한다.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DOTFILES_DIR="$SCRIPT_DIR/dotfiles"
CLAUDE_DIR="$HOME/.claude"

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

echo "[1/5] 설정 파일 설치..."
install_file "$DOTFILES_DIR/CLAUDE.md" "$CLAUDE_DIR/CLAUDE.md"
install_file "$DOTFILES_DIR/settings.json" "$CLAUDE_DIR/settings.json"
install_file "$DOTFILES_DIR/statusline-command.sh" "$CLAUDE_DIR/statusline-command.sh"

echo ""
echo "[2/5] 훅 스크립트 설치..."
install_file "$DOTFILES_DIR/hooks/scripts/block-dangerous.sh" "$CLAUDE_DIR/hooks/scripts/block-dangerous.sh"
install_file "$DOTFILES_DIR/hooks/scripts/save-conv-before-commit.sh" "$CLAUDE_DIR/hooks/scripts/save-conv-before-commit.sh"
chmod +x "$CLAUDE_DIR/hooks/scripts/block-dangerous.sh"
chmod +x "$CLAUDE_DIR/hooks/scripts/save-conv-before-commit.sh"

echo ""
echo "[3/5] 플러그인 메타데이터 설치 (참조용)..."
install_file "$DOTFILES_DIR/meta/installed_plugins.json" "$CLAUDE_DIR/plugins/installed_plugins.json"
install_file "$DOTFILES_DIR/meta/known_marketplaces.json" "$CLAUDE_DIR/plugins/known_marketplaces.json"
install_file "$DOTFILES_DIR/meta/blocklist.json" "$CLAUDE_DIR/plugins/blocklist.json"

echo ""
echo "[4/5] Discord 접근 설정 설치..."
install_file "$DOTFILES_DIR/meta/discord-access.json" "$CLAUDE_DIR/channels/discord/access.json"

echo ""
echo "[5/5] 경로 치환..."
# installed_plugins.json과 known_marketplaces.json의 <HOME> 플레이스홀더를 실제 경로로 변경
sed -i '' "s|<HOME>|$HOME|g" "$CLAUDE_DIR/plugins/installed_plugins.json" 2>/dev/null || \
sed -i "s|<HOME>|$HOME|g" "$CLAUDE_DIR/plugins/installed_plugins.json"
sed -i '' "s|<HOME>|$HOME|g" "$CLAUDE_DIR/plugins/known_marketplaces.json" 2>/dev/null || \
sed -i "s|<HOME>|$HOME|g" "$CLAUDE_DIR/plugins/known_marketplaces.json"

echo ""
echo "=== 설치 완료! ==="
echo ""
echo "⚠️  다음 항목은 수동 설정이 필요합니다:"
echo "  1. Discord 유저 ID: ~/.claude/channels/discord/access.json 에서 allowFrom에 본인 ID 추가"
echo "  2. settings.json의 enabledPlugins: 실제 설치된 플러그인에 맞게 조정"
echo ""
echo "플러그인이 아직 설치되지 않았다면:"
echo "  claude plugin marketplace add --source github:kywpcm/max-plugins"
echo "  claude plugin install dotfiles-claude-code@max-plugins"
