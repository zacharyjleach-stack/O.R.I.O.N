#!/bin/bash
# O.R.I.O.N. DREAM SCHEDULE INSTALLER
# Installs a macOS LaunchAgent to run the Dream State nightly at 3:00 AM.

set -e

echo "============================================================"
echo "🌙 O.R.I.O.N. DREAM SCHEDULE — LaunchAgent Installer"
echo "============================================================"
echo ""

# ── macOS check ──────────────────────────────────────────────────
OS="$(uname -s)"
if [ "$OS" != "Darwin" ]; then
    echo "❌ This script requires macOS (detected: $OS)."
    echo "   launchd is a macOS-only scheduler."
    exit 1
fi
echo "✅ macOS detected"

# ── Locate python3 ──────────────────────────────────────────────
PYTHON3="$(command -v python3 2>/dev/null || true)"
if [ -z "$PYTHON3" ]; then
    echo "❌ python3 not found on PATH. Please install Python 3 first."
    exit 1
fi
echo "✅ python3 found: $PYTHON3"

# ── Resolve project root (parent of this script's directory) ────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
echo "📂 Project root: $PROJECT_ROOT"

RUNNER="$PROJECT_ROOT/scripts/dream_runner.py"
if [ ! -f "$RUNNER" ]; then
    echo "❌ dream_runner.py not found at $RUNNER"
    exit 1
fi
echo "✅ dream_runner.py found"

# ── Ensure state/ directory ─────────────────────────────────────
mkdir -p "$PROJECT_ROOT/state"

# ── Generate LaunchAgent plist ──────────────────────────────────
PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST_PATH="$PLIST_DIR/com.orion.dream.plist"
LABEL="com.orion.dream"

mkdir -p "$PLIST_DIR"

cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${LABEL}</string>

    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON3}</string>
        <string>${PROJECT_ROOT}/scripts/dream_runner.py</string>
    </array>

    <key>WorkingDirectory</key>
    <string>${PROJECT_ROOT}</string>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>3</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>

    <key>StandardOutPath</key>
    <string>${PROJECT_ROOT}/state/dream_logs.txt</string>

    <key>StandardErrorPath</key>
    <string>${PROJECT_ROOT}/state/dream_logs.txt</string>

    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
PLIST

chmod 644 "$PLIST_PATH"
echo "✅ Plist written to $PLIST_PATH (chmod 644)"

# ── Load the agent ──────────────────────────────────────────────
# Unload first if already loaded (ignore errors)
launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load -w "$PLIST_PATH"
echo "✅ LaunchAgent loaded"

# ── Done ────────────────────────────────────────────────────────
echo ""
echo "============================================================"
echo "🌟 O.R.I.O.N. DREAM SCHEDULE INSTALLED SUCCESSFULLY"
echo "============================================================"
echo ""
echo "  Schedule : Every day at 3:00 AM"
echo "  Runner   : $RUNNER"
echo "  Plist    : $PLIST_PATH"
echo "  Logs     : $PROJECT_ROOT/state/dream_logs.txt"
echo "  Status   : $PROJECT_ROOT/state/last_dream.json"
echo ""
echo "  To test now:"
echo "    python3 $RUNNER"
echo ""
echo "  To uninstall:"
echo "    launchctl unload $PLIST_PATH"
echo "    rm $PLIST_PATH"
echo ""
