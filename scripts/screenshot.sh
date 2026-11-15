#!/usr/bin/env bash
# Screenshot a page of the local Odoo site at the design-review sizes.
# Usage: scripts/screenshot.sh <path-or-url> <out-dir> [--dark] [--reduced-motion] [--full]
#   scripts/screenshot.sh /shop /tmp/shots --dark
# Writes <out-dir>/<slug>-<width>[-dark][-rm].png for widths 375, 768, 1440.
set -euo pipefail

target="${1:?usage: screenshot.sh <path-or-url> <out-dir> [--dark] [--reduced-motion] [--full]}"
out="${2:?out dir required}"
shift 2
dark=0; rm=0; full=0
for a in "$@"; do
  case "$a" in
    --dark) dark=1 ;;
    --reduced-motion) rm=1 ;;
    --full) full=1 ;;
    *) echo "unknown flag $a" >&2; exit 1 ;;
  esac
done

[[ "$target" == http* ]] || target="http://127.0.0.1:8069${target}"
slug="$(echo "${target#*://*/}" | tr -c 'a-zA-Z0-9' '-' | sed 's/-\+/-/g; s/^-//; s/-$//')"
slug="${slug:-home}"
mkdir -p "$out"

for w in 375 768 1440; do
  h=$([ "$full" = 1 ] && echo 4000 || ([ "$w" = 375 ] && echo 812 || echo 900))
  flags=(--headless=new --disable-gpu --hide-scrollbars --window-size="${w},${h}"
         --virtual-time-budget=4000)
  suffix=""
  if [ "$dark" = 1 ]; then flags+=(--blink-settings=preferredColorScheme=0); suffix+="-dark"; fi
  if [ "$rm" = 1 ]; then flags+=(--force-prefers-reduced-motion); suffix+="-rm"; fi
  file="$out/${slug}-${w}${suffix}.png"
  timeout 60 google-chrome "${flags[@]}" --screenshot="$file" "$target" >/dev/null 2>&1
  echo "$file"
done
