#!/usr/bin/env bash
# install.sh — install the Token Economy Engine
#   - copy scripts -> ~/.claude/scripts
#   - create the data dir (baseline.csv + feedback-loop.md) at $TE_DIR
#     (default ~/.claude/token-economy)
#   - optionally register a weekly launchd job on macOS
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS_DST="$HOME/.claude/scripts"
DATA_DIR="${TE_DIR:-$HOME/.claude/token-economy}"

echo "-> copy scripts -> $SCRIPTS_DST"
mkdir -p "$SCRIPTS_DST"
cp "$REPO_DIR"/scripts/*.py "$SCRIPTS_DST/"

echo "-> create data dir -> $DATA_DIR"
mkdir -p "$DATA_DIR"
[ -f "$DATA_DIR/baseline.csv" ]     || cp "$REPO_DIR/templates/baseline.csv" "$DATA_DIR/baseline.csv"
[ -f "$DATA_DIR/feedback-loop.md" ] || cp "$REPO_DIR/templates/feedback-loop.md" "$DATA_DIR/feedback-loop.md"

echo
echo "Done. Try:"
echo "   python3 $SCRIPTS_DST/token_waste_scan.py --since 7"
echo "   python3 $SCRIPTS_DST/session_cost.py <session-uuid>"
echo "   TE_DIR=$DATA_DIR python3 $SCRIPTS_DST/token_economy_weekly.py"

# launchd (macOS only)
if [[ "$(uname -s)" == "Darwin" ]]; then
  read -r -p "Register a weekly launchd job (Mondays 09:00)? [y/N] " ans
  if [[ "${ans:-N}" =~ ^[Yy]$ ]]; then
    PLIST_DST="$HOME/Library/LaunchAgents/com.token-economy.weekly.plist"
    sed "s#__HOME__#$HOME#g" "$REPO_DIR/templates/com.token-economy.weekly.plist" > "$PLIST_DST"
    launchctl unload "$PLIST_DST" 2>/dev/null || true
    launchctl load "$PLIST_DST"
    echo "launchd loaded: com.token-economy.weekly"
    echo "   remove with: launchctl unload \"$PLIST_DST\" && rm \"$PLIST_DST\""
  fi
fi
