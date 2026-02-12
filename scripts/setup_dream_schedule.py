#!/usr/bin/env python3
"""
O.R.I.O.N. Dream Schedule — Python LaunchAgent Installer

Generates a macOS LaunchAgent plist that triggers the Dream State
nightly at 3:00 AM, installs it to ~/Library/LaunchAgents/, and
activates it via launchctl.

Default project path: /Volumes/D/O.R.I.O.N/
Override with: python3 setup_dream_schedule.py --project-root /other/path

Usage:
    python3 scripts/setup_dream_schedule.py [--project-root DIR]
"""

import argparse
import os
import platform
import shutil
import stat
import subprocess
import sys
import textwrap


LABEL = "com.orion.dream"
PLIST_FILENAME = f"{LABEL}.plist"


def find_python3() -> str:
    """Locate the python3 interpreter on the system."""
    path = shutil.which("python3")
    if path is None:
        print("❌ python3 not found on PATH. Please install Python 3 first.")
        sys.exit(1)
    return path


def generate_plist(python3: str, project_root: str, log_path: str) -> str:
    """Return the XML content for the LaunchAgent plist."""
    runner = os.path.join(project_root, "scripts", "dream_runner.py")
    return textwrap.dedent(f"""\
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
          "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
        <plist version="1.0">
        <dict>
            <key>Label</key>
            <string>{LABEL}</string>

            <key>ProgramArguments</key>
            <array>
                <string>{python3}</string>
                <string>{runner}</string>
            </array>

            <key>WorkingDirectory</key>
            <string>{project_root}</string>

            <key>StartCalendarInterval</key>
            <dict>
                <key>Hour</key>
                <integer>3</integer>
                <key>Minute</key>
                <integer>0</integer>
            </dict>

            <key>StandardOutPath</key>
            <string>{log_path}</string>

            <key>StandardErrorPath</key>
            <string>{log_path}</string>

            <key>RunAtLoad</key>
            <false/>
        </dict>
        </plist>
    """)


def main() -> None:
    # ── Arguments (parsed first so --help works on any platform) ─
    parser = argparse.ArgumentParser(
        description="Install macOS LaunchAgent for O.R.I.O.N. Dream State"
    )
    parser.add_argument(
        "--project-root",
        default="/Volumes/D/O.R.I.O.N",
        help="Absolute path to the O.R.I.O.N. project (default: /Volumes/D/O.R.I.O.N)",
    )
    args = parser.parse_args()

    # ── Banner ───────────────────────────────────────────────────
    print("=" * 60)
    print("🌙 O.R.I.O.N. DREAM SCHEDULE — LaunchAgent Installer")
    print("=" * 60)
    print()

    # ── macOS check ──────────────────────────────────────────────
    if platform.system() != "Darwin":
        print(f"❌ This script requires macOS (detected: {platform.system()}).")
        print("   launchd is a macOS-only scheduler.")
        sys.exit(1)
    print("✅ macOS detected")

    project_root = os.path.abspath(args.project_root)
    print(f"📂 Project root: {project_root}")

    # ── Validate project structure ───────────────────────────────
    runner_path = os.path.join(project_root, "scripts", "dream_runner.py")
    if not os.path.isfile(runner_path):
        print(f"❌ dream_runner.py not found at {runner_path}")
        sys.exit(1)
    print("✅ dream_runner.py found")

    dream_module = os.path.join(project_root, "modules", "dream.py")
    if not os.path.isfile(dream_module):
        print(f"❌ modules/dream.py not found at {dream_module}")
        sys.exit(1)
    print("✅ modules/dream.py found")

    # ── Locate python3 ──────────────────────────────────────────
    python3 = find_python3()
    print(f"✅ python3 found: {python3}")

    # ── Ensure state/ directory ─────────────────────────────────
    state_dir = os.path.join(project_root, "state")
    os.makedirs(state_dir, exist_ok=True)

    log_path = os.path.join(state_dir, "dream_logs.txt")

    # ── Generate plist ──────────────────────────────────────────
    plist_content = generate_plist(python3, project_root, log_path)

    plist_dir = os.path.expanduser("~/Library/LaunchAgents")
    os.makedirs(plist_dir, exist_ok=True)
    plist_path = os.path.join(plist_dir, PLIST_FILENAME)

    # Unload existing agent if present (ignore errors)
    subprocess.run(
        ["launchctl", "unload", plist_path],
        capture_output=True,
    )

    # Write the plist file
    with open(plist_path, "w", encoding="utf-8") as f:
        f.write(plist_content)

    # Set correct permissions: owner rw, group/other read-only (644)
    os.chmod(plist_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
    print(f"✅ Plist written to {plist_path} (chmod 644)")

    # ── Load the agent ──────────────────────────────────────────
    result = subprocess.run(
        ["launchctl", "load", "-w", plist_path],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"⚠️  launchctl load returned {result.returncode}: {result.stderr.strip()}")
    else:
        print("✅ LaunchAgent loaded")

    # ── Done ────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("🌟 O.R.I.O.N. DREAM SCHEDULE INSTALLED SUCCESSFULLY")
    print("=" * 60)
    print()
    print(f"  Schedule : Every day at 3:00 AM")
    print(f"  Runner   : {runner_path}")
    print(f"  Plist    : {plist_path}")
    print(f"  Logs     : {log_path}")
    print(f"  Status   : {os.path.join(state_dir, 'last_dream.json')}")
    print()
    print("  To test now:")
    print(f"    python3 {runner_path}")
    print()
    print("  To uninstall:")
    print(f"    launchctl unload {plist_path}")
    print(f"    rm {plist_path}")
    print()


if __name__ == "__main__":
    main()
