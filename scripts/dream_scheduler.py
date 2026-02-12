#!/usr/bin/env python3
"""
O.R.I.O.N. Dream Scheduler — Cross-platform nightly dream automation.

A long-running process that triggers modules/dream.py every night at
3:00 AM using the 'schedule' library.  Works on Windows, macOS, and Linux
without platform-specific schedulers (launchd, cron, Task Scheduler).

Usage:
    python3 scripts/dream_scheduler.py [--logs-dir DIR] [--ollama-host URL] [--time HH:MM]

Background execution:

    macOS / Linux:
        nohup python3 scripts/dream_scheduler.py &

    Windows (PowerShell):
        Start-Process -NoNewWindow python "scripts/dream_scheduler.py"

    Windows (cmd):
        start /B python scripts\\dream_scheduler.py

Prerequisites:
    pip install schedule
"""

import argparse
import contextlib
import io
import json
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import schedule
except ImportError:
    print("❌ Missing dependency: schedule")
    print("   Install it with:  pip install schedule")
    sys.exit(1)


# ── Resolve paths ────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Ensure project root is importable
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def log_to_file(log_path: Path, message: str) -> None:
    """Append a timestamped message to the dream log file."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")


def run_dream_cycle(logs_dir: Path, ollama_host: str, state_dir: Path) -> None:
    """Execute a single dream cycle — called by schedule at 3:00 AM."""
    dream_log = state_dir / "dream_logs.txt"
    last_dream = state_dir / "last_dream.json"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    log_to_file(dream_log, "=" * 58)
    log_to_file(dream_log, "Dream cycle started")

    try:
        from modules.dream import DreamState

        dreamer = DreamState(ollama_host=ollama_host)

        # Capture all stdout/stderr produced by DreamState
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()

        with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
            result = dreamer.process_all_logs(str(logs_dir))

        captured_out = stdout_buf.getvalue()
        captured_err = stderr_buf.getvalue()

        with open(dream_log, "a", encoding="utf-8") as f:
            if captured_out:
                f.write(captured_out)
            if captured_err:
                f.write(f"--- stderr ---\n{captured_err}")

        log_to_file(dream_log, f"Result: {json.dumps(result)}")

        summary = {
            "timestamp": timestamp,
            "result": result,
            "logs_dir": str(logs_dir),
            "ollama_host": ollama_host,
        }
        with open(last_dream, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

    except Exception as exc:
        log_to_file(dream_log, f"Dream cycle FAILED: {exc}")

        error_info = {
            "timestamp": timestamp,
            "result": {"status": "error", "reason": str(exc)},
            "logs_dir": str(logs_dir),
            "ollama_host": ollama_host,
        }
        with open(last_dream, "w", encoding="utf-8") as f:
            json.dump(error_info, f, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="O.R.I.O.N. Dream Scheduler — cross-platform nightly automation"
    )
    parser.add_argument(
        "--logs-dir",
        default=None,
        help="Directory containing .log files (default: <project_root>/logs)",
    )
    parser.add_argument(
        "--ollama-host",
        default="http://localhost:11434",
        help="Ollama server URL (default: http://localhost:11434)",
    )
    parser.add_argument(
        "--time",
        default="03:00",
        help="Time to run the dream cycle in HH:MM format (default: 03:00)",
    )
    args = parser.parse_args()

    logs_dir = Path(args.logs_dir) if args.logs_dir else PROJECT_ROOT / "logs"
    state_dir = PROJECT_ROOT / "state"

    # Ensure required directories exist
    logs_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)

    dream_log = state_dir / "dream_logs.txt"

    # ── Banner ───────────────────────────────────────────────────
    print("=" * 60)
    print("  O.R.I.O.N. DREAM SCHEDULER")
    print("=" * 60)
    print(f"  Project root : {PROJECT_ROOT}")
    print(f"  Logs dir     : {logs_dir}")
    print(f"  State dir    : {state_dir}")
    print(f"  Schedule     : Every day at {args.time}")
    print(f"  Ollama       : {args.ollama_host}")
    print(f"  Platform     : {sys.platform}")
    print("=" * 60)
    print()
    print("  Scheduler running. Press Ctrl+C to stop.")
    print()

    log_to_file(dream_log, f"Scheduler started (schedule: daily at {args.time})")

    # ── Schedule the job ─────────────────────────────────────────
    schedule.every().day.at(args.time).do(
        run_dream_cycle, logs_dir, args.ollama_host, state_dir
    )

    # ── Graceful shutdown on SIGINT / SIGTERM ────────────────────
    def handle_shutdown(signum: int, _frame: object) -> None:
        sig_name = signal.Signals(signum).name
        print(f"\n  Received {sig_name}. Shutting down scheduler.")
        log_to_file(dream_log, f"Scheduler stopped ({sig_name})")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # ── Main loop ────────────────────────────────────────────────
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
