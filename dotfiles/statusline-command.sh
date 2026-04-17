#!/bin/sh
input=$(cat)
cwd=$(echo "$input" | jq -r '.cwd')
ctx_pct=$(echo "$input" | jq -r '.context_window.used_percentage // 0' | cut -d. -f1)
rate_5h=$(echo "$input" | jq -r '.rate_limits.five_hour.used_percentage // 0' | cut -d. -f1)
rate_7d=$(echo "$input" | jq -r '.rate_limits.seven_day.used_percentage // 0' | cut -d. -f1)
reset_5h=$(echo "$input" | jq -r '.rate_limits.five_hour.resets_at // 0' | cut -d. -f1)
reset_7d=$(echo "$input" | jq -r '.rate_limits.seven_day.resets_at // 0' | cut -d. -f1)
model=$(echo "$input" | jq -r '.model.display_name // "Unknown"' | sed 's/ context)/)/')

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

printf '%s\nCtx %b%s%%\033[0m | 5h %b%s%%\033[0m (%s) | 7d %b%s%%\033[0m (%s) | %s' \
  "$dir_part" \
  "$ctx_color" "$ctx_pct" \
  "$color_5h" "$rate_5h" "$remain_5h" \
  "$color_7d" "$rate_7d" "$remain_7d" \
  "$model"
