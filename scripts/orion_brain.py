#!/usr/bin/env python3
"""
O.R.I.O.N. BRAIN -- Unified Python Brain Launcher
==================================================
Auto-starts all Python brain subsystems as a single long-running process.

Subsystems:
  - The Hippocampus (core/memory.py)    -- Vector memory with ChromaDB
  - The Dream State (modules/dream.py)  -- Nightly log consolidation at 3 AM
  - The Scout (modules/scout.py)        -- GitHub release monitoring (hourly)
  - The Executive (modules/executive.py) -- Vision Loop + OS automation

Usage:
    python scripts/orion_brain.py
    python scripts/orion_brain.py --trust-mode          # Skip action confirmations
    python scripts/orion_brain.py --no-dream             # Disable dream scheduler
    python scripts/orion_brain.py --no-vision            # Disable vision loop
    python scripts/orion_brain.py --no-scout             # Disable scout
"""

import argparse
import json
import os
import signal
import sys
import time
import threading
from datetime import datetime
from pathlib import Path

# -- Resolve project root ------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# -- State directories ---------------------------------------------------------
STATE_DIR = PROJECT_ROOT / "state"
LOGS_DIR = PROJECT_ROOT / "logs"
STATE_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

BRAIN_LOG = STATE_DIR / "brain.log"
BRAIN_PID = STATE_DIR / "brain.pid"

# -- Logging -------------------------------------------------------------------
def log(tag, msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{tag}] {msg}"
    print(line)
    try:
        with open(BRAIN_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def banner():
    print()
    print("  +=======================================================+")
    print("  |                                                       |")
    print("  |         O.R.I.O.N. BRAIN -- All Systems Boot          |")
    print("  |                                                       |")
    print("  +=======================================================+")
    print()


# ==============================================================================
#  SUBSYSTEM: HIPPOCAMPUS (Memory)
# ==============================================================================
def boot_memory():
    """Initialize the vector memory system."""
    try:
        from core.memory import get_memory
        mem = get_memory()
        stats = mem.get_stats()
        log("MEMORY", f"Hippocampus online. {stats['total_memories']} memories loaded.")
        return mem
    except Exception as e:
        log("MEMORY", f"Failed to initialize: {e}")
        return None


# ==============================================================================
#  SUBSYSTEM: DREAM STATE (Nightly Learning)
# ==============================================================================
def boot_dream(ollama_host):
    """Start the dream scheduler in a background thread."""
    try:
        import schedule as sched_lib
    except ImportError:
        log("DREAM", "schedule library not installed. Dream disabled.")
        return None

    def run_dream_cycle():
        try:
            from modules.dream import DreamState
            log("DREAM", "Dream cycle starting...")
            dreamer = DreamState(ollama_host=ollama_host)
            result = dreamer.process_all_logs(str(LOGS_DIR))
            log("DREAM", f"Dream cycle complete: {json.dumps(result)}")
        except Exception as e:
            log("DREAM", f"Dream cycle failed: {e}")

    # Schedule at 3:00 AM daily
    sched_lib.every().day.at("03:00").do(run_dream_cycle)
    log("DREAM", "Dream State armed. Next dream cycle at 03:00.")

    def scheduler_loop():
        while True:
            sched_lib.run_pending()
            time.sleep(30)

    t = threading.Thread(target=scheduler_loop, daemon=True, name="dream-scheduler")
    t.start()
    return t


# ==============================================================================
#  SUBSYSTEM: SCOUT (GitHub Release Monitor)
# ==============================================================================
def boot_scout():
    """Start the scout monitoring in a background thread (checks hourly)."""
    try:
        from modules.scout import Scout
    except ImportError as e:
        log("SCOUT", f"Failed to import Scout: {e}")
        return None

    def scout_loop():
        state_file = str(STATE_DIR / "scout_state.json")
        while True:
            try:
                scout = Scout(state_file=state_file)
                updates = scout.check_all()
                if updates:
                    log("SCOUT", f"Found {len(updates)} update(s) available")
                    for u in updates:
                        log("SCOUT", f"  {u.get('repo', '?')}: {u.get('current', '?')} -> {u.get('latest', '?')}")
                else:
                    log("SCOUT", "All tracked repos up to date.")
            except Exception as e:
                log("SCOUT", f"Scout check failed: {e}")
            time.sleep(3600)  # Check every hour

    t = threading.Thread(target=scout_loop, daemon=True, name="scout-monitor")
    t.start()
    log("SCOUT", "Scout armed. Checking for updates every hour.")
    return t


# ==============================================================================
#  SUBSYSTEM: EXECUTIVE (Vision Loop + OS Control)
# ==============================================================================
def boot_executive(trust_mode=False):
    """Initialize the Executive module with Vision Loop."""
    try:
        from modules.executive import OrionExecutive
        executive = OrionExecutive(trust_mode=trust_mode)
        stats = executive.get_stats()
        log("EXECUTIVE", f"Executive online. OS: {stats.get('os', '?')}")
        if stats.get("vision_backend"):
            log("VISION", f"Vision Loop active via {stats['vision_backend']}")
        else:
            log("VISION", "Vision Loop inactive (no vision backend available)")
        if stats.get("gui_available"):
            log("EXECUTIVE", "GUI control (mouse/keyboard) available")
        else:
            log("EXECUTIVE", "GUI control unavailable (pyautogui not installed)")
        return executive
    except Exception as e:
        log("EXECUTIVE", f"Failed to initialize: {e}")
        return None


# ==============================================================================
#  HEALTH CHECK SERVER (optional, for gateway integration)
# ==============================================================================
def start_health_server(port, subsystems):
    """Start a tiny HTTP health endpoint so the Node gateway can check brain status."""
    try:
        from http.server import HTTPServer, BaseHTTPRequestHandler

        class HealthHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                status = {
                    "status": "running",
                    "pid": os.getpid(),
                    "uptime_seconds": int(time.time() - subsystems.get("start_time", time.time())),
                    "subsystems": {
                        "memory": subsystems.get("memory") is not None,
                        "dream": subsystems.get("dream") is not None,
                        "scout": subsystems.get("scout") is not None,
                        "executive": subsystems.get("executive") is not None,
                        "vision": bool(
                            subsystems.get("executive")
                            and getattr(subsystems["executive"], "_vision_backend", None)
                        ),
                    },
                }
                body = json.dumps(status).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):
                pass  # Suppress request logging

        server = HTTPServer(("127.0.0.1", port), HealthHandler)
        t = threading.Thread(target=server.serve_forever, daemon=True, name="health-server")
        t.start()
        log("HEALTH", f"Health endpoint listening on http://127.0.0.1:{port}/")
        return server
    except Exception as e:
        log("HEALTH", f"Failed to start health server: {e}")
        return None


# ==============================================================================
#  MAIN
# ==============================================================================
def main():
    parser = argparse.ArgumentParser(description="O.R.I.O.N. Brain -- unified launcher")
    parser.add_argument("--trust-mode", action="store_true", help="Skip confirmation prompts for OS actions")
    parser.add_argument("--no-dream", action="store_true", help="Disable dream scheduler")
    parser.add_argument("--no-vision", action="store_true", help="Disable vision/executive module")
    parser.add_argument("--no-scout", action="store_true", help="Disable scout monitoring")
    parser.add_argument("--ollama-host", default="http://localhost:11434", help="Ollama server URL")
    parser.add_argument("--health-port", type=int, default=18790, help="Health check HTTP port (default: 18790)")
    args = parser.parse_args()

    banner()

    # Write PID file
    with open(BRAIN_PID, "w") as f:
        f.write(str(os.getpid()))
    log("BRAIN", f"PID {os.getpid()} written to {BRAIN_PID}")
    log("BRAIN", f"Project root: {PROJECT_ROOT}")
    log("BRAIN", f"Ollama host: {args.ollama_host}")

    subsystems = {"start_time": time.time()}

    # -- Boot each subsystem ---------------------------------------------------
    log("BRAIN", "Booting subsystems...")
    print()

    # 1. Memory (always on)
    log("BRAIN", "[1/4] Hippocampus (Memory)...")
    subsystems["memory"] = boot_memory()

    # 2. Dream State
    if not args.no_dream:
        log("BRAIN", "[2/4] Dream State (Nightly Learning)...")
        subsystems["dream"] = boot_dream(args.ollama_host)
    else:
        log("BRAIN", "[2/4] Dream State -- SKIPPED")
        subsystems["dream"] = None

    # 3. Scout
    if not args.no_scout:
        log("BRAIN", "[3/4] Scout (GitHub Monitor)...")
        subsystems["scout"] = boot_scout()
    else:
        log("BRAIN", "[3/4] Scout -- SKIPPED")
        subsystems["scout"] = None

    # 4. Executive + Vision Loop
    if not args.no_vision:
        log("BRAIN", "[4/4] Executive + Vision Loop...")
        subsystems["executive"] = boot_executive(trust_mode=args.trust_mode)
    else:
        log("BRAIN", "[4/4] Executive + Vision Loop -- SKIPPED")
        subsystems["executive"] = None

    # -- Health endpoint -------------------------------------------------------
    start_health_server(args.health_port, subsystems)

    # -- Summary ---------------------------------------------------------------
    print()
    print("  +=======================================================+")
    active = sum(1 for k in ["memory", "dream", "scout", "executive"] if subsystems.get(k))
    print(f"  |   O.R.I.O.N. Brain running -- {active}/4 subsystems active    |")
    print("  +=======================================================+")
    print()
    log("BRAIN", f"All systems go. {active}/4 subsystems active.")
    log("BRAIN", f"Health: http://127.0.0.1:{args.health_port}/")
    log("BRAIN", "Press Ctrl+C to shut down.")
    print()

    # -- Graceful shutdown -----------------------------------------------------
    def shutdown(signum, _frame):
        sig_name = signal.Signals(signum).name if hasattr(signal, "Signals") else str(signum)
        log("BRAIN", f"Received {sig_name}. Shutting down...")
        if BRAIN_PID.exists():
            BRAIN_PID.unlink()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # -- Keep alive (all work is in daemon threads) ----------------------------
    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()
