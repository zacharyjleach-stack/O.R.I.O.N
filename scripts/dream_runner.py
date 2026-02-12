#!/usr/bin/env python3
"""
O.R.I.O.N. Dream Runner — Nightly entry point for the Dream State.

Designed to be invoked by macOS launchd (or manually) to consolidate
daily logs into long-term vector memories.

Usage:
    python3 scripts/dream_runner.py [--logs-dir DIR] [--ollama-host URL]
"""

import argparse
import contextlib
import io
import json
import os
import sys
from datetime import datetime


def main() -> int:
    parser = argparse.ArgumentParser(
        description="O.R.I.O.N. Dream Runner — nightly log consolidation"
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
    args = parser.parse_args()

    # Resolve project root (parent of scripts/)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Ensure project root is on sys.path so modules/core imports work
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    logs_dir = args.logs_dir or os.path.join(project_root, "logs")
    state_dir = os.path.join(project_root, "state")

    # Ensure required directories exist
    os.makedirs(logs_dir, exist_ok=True)
    os.makedirs(state_dir, exist_ok=True)

    dream_log_path = os.path.join(state_dir, "dream_logs.txt")
    last_dream_path = os.path.join(state_dir, "last_dream.json")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        from modules.dream import DreamState

        dreamer = DreamState(ollama_host=args.ollama_host)

        # Capture all stdout/stderr produced by DreamState
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()

        with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
            result = dreamer.process_all_logs(logs_dir)

        captured_out = stdout_buf.getvalue()
        captured_err = stderr_buf.getvalue()

        # Append to application-level dream log
        with open(dream_log_path, "a", encoding="utf-8") as f:
            f.write(f"\n{'=' * 60}\n")
            f.write(f"[{timestamp}] Dream cycle started\n")
            f.write(f"{'=' * 60}\n")
            if captured_out:
                f.write(captured_out)
            if captured_err:
                f.write(f"--- stderr ---\n{captured_err}")
            f.write(f"[{timestamp}] Result: {json.dumps(result)}\n")

        # Write quick-status JSON
        summary = {
            "timestamp": timestamp,
            "result": result,
            "logs_dir": logs_dir,
            "ollama_host": args.ollama_host,
        }
        with open(last_dream_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        return 0

    except Exception as exc:
        # Ensure launchd never sees an unhandled crash
        error_info = {
            "timestamp": timestamp,
            "result": {"status": "error", "reason": str(exc)},
            "logs_dir": logs_dir,
            "ollama_host": args.ollama_host,
        }

        with open(dream_log_path, "a", encoding="utf-8") as f:
            f.write(f"\n{'=' * 60}\n")
            f.write(f"[{timestamp}] Dream cycle FAILED: {exc}\n")
            f.write(f"{'=' * 60}\n")

        with open(last_dream_path, "w", encoding="utf-8") as f:
            json.dump(error_info, f, indent=2)

        return 1


if __name__ == "__main__":
    sys.exit(main())
