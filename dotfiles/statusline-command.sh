#!/bin/sh
input=$(cat)
cwd=$(echo "$input" | jq -r '.cwd')
ctx_pct=$(echo "$input" | jq -r '.context_window.used_percentage // 0' | cut -d. -f1)
rate_5h=$(echo "$input" | jq -r '.rate_limits.five_hour.used_percentage // 0' | cut -d. -f1)
rate_7d=$(echo "$input" | jq -r '.rate_limits.seven_day.used_percentage // 0' | cut -d. -f1)
reset_5h=$(echo "$input" | jq -r '.rate_limits.five_hour.resets_at // 0' | cut -d. -f1)
reset_7d=$(echo "$input" | jq -r '.rate_limits.seven_day.resets_at // 0' | cut -d. -f1)
model=$(echo "$input" | jq -r '.model.display_name // "Unknown"' | sed 's/ context)/)/')
session_id=$(echo "$input" | jq -r '.session_id // ""')
transcript_path=$(echo "$input" | jq -r '.transcript_path // ""')

# Effort level: /effort 슬래시 명령은 statusline JSON에 직접 노출되지 않지만,
# 실행되면 transcript JSONL에 "Set effort level to <X> ..." 라인이 남는다.
# 명시적으로 설정한 세션에서만 표시하고, 흔적이 없으면 아무것도 붙이지 않는다
# (내부 기본값을 추측해서 잘못 표시하지 않기 위함).
if [ -z "$transcript_path" ] && [ -n "$session_id" ] && [ -n "$cwd" ]; then
  # Claude Code는 프로젝트 디렉터리명에서 '/'와 '.'을 모두 '-'로 치환한다.
  encoded_cwd=$(printf '%s' "$cwd" | sed 's|[/.]|-|g')
  transcript_path="$HOME/.claude/projects/${encoded_cwd}/${session_id}.jsonl"
fi

# 전역 effort: settings.json의 .effortLevel — 다른 세션에서 /effort high 같은 영구 설정을
# 바꿔도 모든 세션에 동일하게 반영된다 (이게 Claude Code의 진짜 저장소).
global_effort=$(jq -r '.effortLevel // ""' "$HOME/.claude/settings.json" 2>/dev/null)

# 세션 전용 오버라이드: /effort max 같은 "this session only" 레벨은 settings.json을
# 건드리지 않고 transcript에만 기록된다. transcript의 마지막 "Set effort level to ..." 라인이
# (this session only)를 포함할 때만 세션 오버라이드로 인정. 글로벌 변경 뒤 기록이 있으면
# 세션 오버라이드는 무효가 됨 (마지막 라인이 괄호 없음이 되므로).
session_effort=""
if [ -f "$transcript_path" ] && [ -n "$session_id" ]; then
  effort_cache="${TMPDIR:-/tmp}/claude-effort-${session_id}"
  if [ -f "$effort_cache" ] && [ "$effort_cache" -nt "$transcript_path" ]; then
    session_effort=$(cat "$effort_cache" 2>/dev/null)
  else
    last_line=$(tail -n 2000 "$transcript_path" 2>/dev/null \
      | grep -E 'Set effort level to [a-z]+' \
      | tail -1)
    if printf '%s' "$last_line" | grep -qF '(this session only)'; then
      session_effort=$(printf '%s' "$last_line" \
        | grep -oE 'Set effort level to [a-z]+' \
        | awk '{print $NF}')
    fi
    printf '%s' "$session_effort" > "$effort_cache" 2>/dev/null
  fi
fi

# 세션 오버라이드가 있으면 그것, 아니면 전역값.
effort="${session_effort:-$global_effort}"

# git 브랜치 (symbolic-ref는 git 2.18+에서도 동작)
branch=$(git -C "$cwd" --no-optional-locks symbolic-ref --short HEAD 2>/dev/null)

# 색상 선택 함수
pick_color() {
  pct=$1
  if [ "$pct" -ge 90 ]; then printf '\033[31m'
  elif [ "$pct" -ge 70 ]; then printf '\033[33m'
  else printf '\033[32m'
  fi
}

# 남은 시간 포맷 함수: resets_at -> "Xh Ym"
fmt_remaining() {
  reset_at=$1
  now=$(date +%s)
  diff=$((reset_at - now))
  if [ "$diff" -le 0 ] || [ "$reset_at" -eq 0 ]; then
    printf '%s' '--'
    return
  fi
  days=$((diff / 86400))
  hours=$(( (diff % 86400) / 3600 ))
  mins=$(( (diff % 3600) / 60 ))
  if [ "$days" -gt 0 ]; then
    printf '%dd %dh' "$days" "$hours"
  elif [ "$hours" -gt 0 ]; then
    printf '%dh %dm' "$hours" "$mins"
  else
    printf '%dm' "$mins"
  fi
}

ctx_color=$(pick_color "$ctx_pct")
color_5h=$(pick_color "$rate_5h")
color_7d=$(pick_color "$rate_7d")
remain_5h=$(fmt_remaining "$reset_5h")
remain_7d=$(fmt_remaining "$reset_7d")

# 홈 디렉토리를 ~로 축약 (zsh %~ 동작과 동일)
home="$HOME"
short_cwd=$(echo "$cwd" | sed "s|^$home|~|")

# 디렉토리 + 브랜치
if [ -n "$branch" ]; then
  dir_part=$(printf '\033[36m%s\033[0m\033[32m (%s)\033[0m' "$short_cwd" "$branch")
else
  dir_part=$(printf '\033[36m%s\033[0m' "$short_cwd")
fi

# 모델 + effort 조합: effort 흔적 있으면 "<model> | <effort>", 없으면 모델만.
if [ -n "$effort" ]; then
  model_part="${model} | ${effort}"
else
  model_part="$model"
fi

printf '%s\nCtx %b%s%%\033[0m | 5h %b%s%%\033[0m (%s) | 7d %b%s%%\033[0m (%s) | %s' \
  "$dir_part" \
  "$ctx_color" "$ctx_pct" \
  "$color_5h" "$rate_5h" "$remain_5h" \
  "$color_7d" "$rate_7d" "$remain_7d" \
  "$model_part"
