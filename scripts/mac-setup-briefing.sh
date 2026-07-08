#!/usr/bin/env bash
# Mac setup — installs morning briefing LaunchAgent (runs on login)
# Run this once on your Mac after cloning the repo.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USER_NAME="$(whoami)"
PLIST_SRC="$REPO_DIR/scripts/com.jirani.morning-briefing.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.jirani.morning-briefing.plist"
LOG_FILE="$REPO_DIR/todos/briefing.log"

mkdir -p "$HOME/Library/LaunchAgents"
mkdir -p "$REPO_DIR/todos"

# Replace placeholders in the plist with real paths
sed -e "s|__REPO_PATH__|$REPO_DIR|g" \
    -e "s|__USER__|$USER_NAME|g" \
    "$PLIST_SRC" > "$PLIST_DST"

echo "Plist written to: $PLIST_DST"

# Load the LaunchAgent (runs on next login)
launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load "$PLIST_DST"

echo "LaunchAgent loaded."
echo ""
echo "To test now:    bash $REPO_DIR/scripts/morning-briefing.sh"
echo "To view log:    cat $LOG_FILE"
echo "To stop:         launchctl unload $PLIST_DST"
echo "To uninstall:    rm $PLIST_DST && launchctl unload $PLIST_DST"
