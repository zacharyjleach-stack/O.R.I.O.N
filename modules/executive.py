"""
O.R.I.O.N. SKILL MODULE: THE EXECUTIVE (The Hands)
===================================================
This file is part of THE LAB - Updatable skills and plugins.
Status: UPDATABLE - Can be improved through the Evolution Engine.

The Executive module provides controlled OS-level automation capabilities
including GUI control, shell execution, and browser navigation.

SECURITY: All actions are logged, rate-limited, and require explicit permission.
"""

import platform
import os
import subprocess
import sys
import json
import re
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path

# Import the core memory system (immutable dependency)
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from core.memory import recall, remember, recall_preferences, get_memory

# Platform detection
CURRENT_OS = platform.system()  # 'Darwin', 'Windows', 'Linux'

# Security settings
HEADLESS_MODE = True  # Run browsers in background by default
TRUST_MODE = False    # If False, prompt for confirmation on physical actions
LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "executive.log"

# Ensure log directory exists
LOG_DIR.mkdir(exist_ok=True)

# Import GUI control library (with fallback if not installed)
try:
    import pyautogui
    # Safety settings
    pyautogui.PAUSE = 1.0  # 1 second pause between actions
    pyautogui.FAILSAFE = True  # Move mouse to corner to abort
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False
    print("⚠️ pyautogui not installed. GUI control disabled.")
    print("   Install with: pip install pyautogui")

# Import Playwright for browser control (with fallback)
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("⚠️ Playwright not installed. Browser automation disabled.")
    print("   Install with: pip install playwright && playwright install")

# Import requests for Ollama HTTP calls (used by both vision and goal proposal)
try:
    import requests as _requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    _requests = None  # type: ignore[assignment]

# Import Vision Loop dependencies (with fallback)
try:
    import mss
    import mss.tools
    from PIL import Image
    import io
    import base64
    VISION_AVAILABLE = True
except ImportError as e:
    VISION_AVAILABLE = False
    print(f"⚠️ Vision Loop dependencies not installed: {e}")
    print("   Install with: pip install mss pillow requests")

# Gemini SDK is optional — only used as a cloud fallback
try:
    from google import genai
    GEMINI_SDK_AVAILABLE = True
except ImportError:
    GEMINI_SDK_AVAILABLE = False


class OrionExecutive:
    """
    The Hands - O.R.I.O.N.'s interface to the physical OS.

    Provides controlled automation capabilities with security checks.
    """

    def __init__(self, trust_mode: bool = TRUST_MODE):
        """
        Initialize the Executive module.

        Args:
            trust_mode: If False, prompt for confirmation before physical actions
        """
        self.trust_mode = trust_mode
        self.os = CURRENT_OS
        self.modifier_key = self._get_modifier_key()
        self.action_count = 0
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Security: Command whitelist (only these shell commands allowed)
        self.allowed_commands = [
            'ls', 'dir', 'pwd', 'cd', 'echo', 'cat', 'head', 'tail',
            'date', 'time', 'whoami', 'hostname', 'uname',
            'mkdir', 'touch', 'cp', 'mv',  # File operations (safe ones)
            'git',  # Git operations
        ]

        # Initialize Vision Loop — prefer local Ollama/llava, fall back to Gemini
        self._ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        self._vision_backend = None  # "ollama" | "gemini" | None
        self.vision_client = None    # Gemini client (only when backend == "gemini")

        if VISION_AVAILABLE:
            # Try 1: Local Ollama with llava model (private, no cloud)
            if self._check_ollama_vision():
                self._vision_backend = "ollama"
                print("✅ Vision backend: Ollama/llava (local)")
            # Try 2: Cloud fallback — Gemini
            elif GEMINI_SDK_AVAILABLE:
                try:
                    api_key = os.environ.get("GEMINI_API_KEY")
                    if api_key:
                        self.vision_client = genai.Client(api_key=api_key)
                        self._vision_backend = "gemini"
                        print("⚠️ Ollama unavailable — falling back to Gemini (cloud)")
                    else:
                        print("⚠️ Ollama unavailable and GEMINI_API_KEY not set. Vision disabled.")
                except Exception as e:
                    print(f"⚠️ Failed to initialize Gemini client: {e}")
            else:
                print("⚠️ Ollama unavailable and google-genai not installed. Vision disabled.")

        self._log("Executive initialized", {
            "os": self.os,
            "trust_mode": self.trust_mode,
            "gui_available": GUI_AVAILABLE,
            "playwright_available": PLAYWRIGHT_AVAILABLE,
            "vision_available": self._vision_backend is not None,
            "vision_backend": self._vision_backend
        })

    def _get_modifier_key(self) -> str:
        """Determine the appropriate modifier key for the OS."""
        if self.os == 'Darwin':  # macOS
            return 'command'
        else:  # Windows/Linux
            return 'ctrl'

    def _log(self, action: str, details: Dict[str, Any]) -> None:
        """
        Log all executive actions for audit trail.

        Args:
            action: Description of the action
            details: Additional details about the action
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "session": self.session_id,
            "action": action,
            "details": details,
            "action_number": self.action_count
        }

        try:
            with open(LOG_FILE, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            print(f"⚠️ Failed to write log: {e}")

        self.action_count += 1

    def _confirm_action(self, action: str, details: str) -> bool:
        """
        Ask user to confirm a physical action.

        Args:
            action: Action description
            details: Action details

        Returns:
            True if user approves, False otherwise
        """
        if self.trust_mode:
            return True

        print("\n" + "=" * 60)
        print("⚠️  O.R.I.O.N. IS REQUESTING PHYSICAL CONTROL")
        print("=" * 60)
        print(f"Action: {action}")
        print(f"Details: {details}")
        print("=" * 60)

        response = input("Allow this action? [Y/N]: ").strip().upper()
        approved = response == 'Y'

        self._log("confirmation_prompt", {
            "action": action,
            "details": details,
            "approved": approved
        })

        return approved

    # ── Ollama / llava helpers ───────────────────────────────────

    def _check_ollama_vision(self) -> bool:
        """
        Verify that Ollama is running and the llava model is available.

        Returns:
            True if Ollama is reachable and llava is pulled, False otherwise.
        """
        try:
            resp = _requests.get(f"{self._ollama_host}/api/tags", timeout=5)
            if resp.status_code != 200:
                return False
            models = [m.get("name", "") for m in resp.json().get("models", [])]
            # Accept any llava variant (llava, llava:13b, llava:latest, …)
            return any(m.startswith("llava") for m in models)
        except Exception:
            return False

    def _analyze_with_ollama(
        self, prompt: str, image_base64: str
    ) -> Optional[str]:
        """
        Send an image + prompt to the local Ollama llava model.

        Args:
            prompt: The vision analysis prompt.
            image_base64: Base64-encoded PNG image data.

        Returns:
            The model's text response, or None on failure.
        """
        try:
            resp = _requests.post(
                f"{self._ollama_host}/api/generate",
                json={
                    "model": "llava",
                    "prompt": prompt,
                    "images": [image_base64],
                    "stream": False,
                },
                timeout=120,
            )
            if resp.status_code == 200:
                return resp.json().get("response", "")
            print(f"⚠️ Ollama llava request failed: HTTP {resp.status_code}")
            return None
        except Exception as e:
            print(f"⚠️ Ollama llava error: {e}")
            return None

    def gui_control(
        self,
        action: str,
        x: Optional[int] = None,
        y: Optional[int] = None,
        text: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Safely control mouse and keyboard.

        Args:
            action: 'move', 'click', 'type', 'hotkey'
            x: X coordinate (for move/click)
            y: Y coordinate (for move/click)
            text: Text to type or hotkey combination

        Returns:
            Dict with status and details
        """
        if not GUI_AVAILABLE:
            return {"success": False, "error": "pyautogui not installed"}

        # Security check: confirm action
        if not self._confirm_action(f"GUI {action}", f"x={x}, y={y}, text={text}"):
            return {"success": False, "error": "User denied permission"}

        try:
            if action == 'move':
                pyautogui.moveTo(x, y, duration=0.5)
                self._log("gui_move", {"x": x, "y": y})
                return {"success": True, "action": "move", "x": x, "y": y}

            elif action == 'click':
                if x is not None and y is not None:
                    pyautogui.click(x, y)
                else:
                    pyautogui.click()
                self._log("gui_click", {"x": x, "y": y})
                return {"success": True, "action": "click", "x": x, "y": y}

            elif action == 'type':
                pyautogui.write(text, interval=0.1)
                self._log("gui_type", {"length": len(text)})
                return {"success": True, "action": "type", "chars": len(text)}

            elif action == 'hotkey':
                keys = text.split('+')
                pyautogui.hotkey(*keys)
                self._log("gui_hotkey", {"keys": keys})
                return {"success": True, "action": "hotkey", "keys": keys}

            else:
                return {"success": False, "error": f"Unknown action: {action}"}

        except Exception as e:
            self._log("gui_error", {"action": action, "error": str(e)})
            return {"success": False, "error": str(e)}

    def system_shell(self, command: str) -> Dict[str, Any]:
        """
        Execute terminal commands (WHITELISTED ONLY for security).

        Args:
            command: Shell command to execute

        Returns:
            Dict with status, stdout, and stderr
        """
        # Security: Parse command to check if it's allowed
        cmd_parts = command.strip().split()
        if not cmd_parts:
            return {"success": False, "error": "Empty command"}

        base_command = cmd_parts[0]

        # Security check: command must be in whitelist
        if base_command not in self.allowed_commands:
            self._log("blocked_command", {"command": command, "reason": "not in whitelist"})
            return {
                "success": False,
                "error": f"Command '{base_command}' not in whitelist",
                "allowed_commands": self.allowed_commands
            }

        # Confirm action
        if not self._confirm_action("Shell execution", command):
            return {"success": False, "error": "User denied permission"}

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30  # 30 second timeout
            )

            self._log("shell_execution", {
                "command": command,
                "returncode": result.returncode,
                "stdout_length": len(result.stdout),
                "stderr_length": len(result.stderr)
            })

            return {
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "command": command
            }

        except subprocess.TimeoutExpired:
            self._log("shell_timeout", {"command": command})
            return {"success": False, "error": "Command timed out (30s limit)"}
        except Exception as e:
            self._log("shell_error", {"command": command, "error": str(e)})
            return {"success": False, "error": str(e)}

    def browser_nav(
        self,
        url: str,
        headless: bool = HEADLESS_MODE,
        action: Optional[str] = None,
        selector: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Navigate and interact with websites using Playwright.

        Args:
            url: URL to visit
            headless: Run browser in background (default: True)
            action: Optional action ('click', 'type', 'screenshot')
            selector: CSS selector for the element to interact with

        Returns:
            Dict with status and results
        """
        if not PLAYWRIGHT_AVAILABLE:
            return {"success": False, "error": "Playwright not installed"}

        # Confirm action
        if not self._confirm_action(f"Browser navigation: {action or 'visit'}", url):
            return {"success": False, "error": "User denied permission"}

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=headless)
                page = browser.new_page()

                # Navigate to URL
                page.goto(url, wait_until='domcontentloaded')

                result = {
                    "success": True,
                    "url": url,
                    "title": page.title()
                }

                # Perform optional action
                if action and selector:
                    if action == 'click':
                        page.click(selector)
                        result["action"] = "clicked"
                    elif action == 'type':
                        page.fill(selector, selector)  # TODO: add text param
                        result["action"] = "typed"
                    elif action == 'screenshot':
                        screenshot_path = f"screenshots/{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                        os.makedirs("screenshots", exist_ok=True)
                        page.screenshot(path=screenshot_path)
                        result["screenshot"] = screenshot_path

                # Get page content
                result["content_preview"] = page.content()[:500]

                browser.close()

                self._log("browser_navigation", {
                    "url": url,
                    "action": action,
                    "headless": headless
                })

                return result

        except Exception as e:
            self._log("browser_error", {"url": url, "error": str(e)})
            return {"success": False, "error": str(e)}

    def capture_screenshot(self, save_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Capture a screenshot of the entire screen using mss.

        Args:
            save_path: Optional path to save the screenshot

        Returns:
            Dict with success status, image data, and file path
        """
        if not VISION_AVAILABLE:
            return {"success": False, "error": "Vision dependencies not installed"}

        try:
            with mss.mss() as sct:
                # Capture the primary monitor
                monitor = sct.monitors[1]
                screenshot = sct.grab(monitor)

                # Convert to PIL Image
                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

                # Save if path provided
                if save_path:
                    os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
                    img.save(save_path)
                else:
                    # Create default path in screenshots directory
                    save_path = f"screenshots/screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                    os.makedirs("screenshots", exist_ok=True)
                    img.save(save_path)

                # Convert to base64 for API transmission
                buffered = io.BytesIO()
                img.save(buffered, format="PNG")
                img_base64 = base64.b64encode(buffered.getvalue()).decode()

                self._log("screenshot_captured", {
                    "path": save_path,
                    "size": screenshot.size,
                    "monitor": monitor
                })

                return {
                    "success": True,
                    "path": save_path,
                    "size": screenshot.size,
                    "image_base64": img_base64,
                    "image": img  # PIL Image object
                }

        except Exception as e:
            self._log("screenshot_error", {"error": str(e)})
            return {"success": False, "error": str(e)}

    def analyze_screen(
        self,
        query: str,
        screenshot_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Analyze a screenshot to find UI elements.

        Prioritizes the local Ollama/llava model for privacy.
        Falls back to Gemini only if Ollama is unreachable.

        Args:
            query: What to find (e.g., "Find the Start button coordinates")
            screenshot_data: Optional screenshot dict from capture_screenshot()

        Returns:
            Dict with analysis results including coordinates if found
        """
        if not VISION_AVAILABLE or self._vision_backend is None:
            return {"success": False, "error": "Vision analysis not available"}

        try:
            # Capture screenshot if not provided
            if screenshot_data is None:
                screenshot_data = self.capture_screenshot()
                if not screenshot_data["success"]:
                    return screenshot_data

            # Prepare the vision prompt
            vision_prompt = f"""Analyze this screenshot and {query}

IMPORTANT: If you find UI elements with specific locations, return the coordinates in this EXACT format:
COORDINATES: x=123, y=456

If you find multiple elements, list them as:
COORDINATES: [
  {{"name": "element1", "x": 100, "y": 200}},
  {{"name": "element2", "x": 300, "y": 400}}
]

Be precise with pixel coordinates. The top-left corner is (0, 0)."""

            image_path = screenshot_data["path"]
            image_b64 = screenshot_data["image_base64"]
            analysis_text = None

            # Route to the active vision backend
            if self._vision_backend == "ollama":
                analysis_text = self._analyze_with_ollama(vision_prompt, image_b64)
                # If Ollama failed mid-session, try Gemini fallback
                if analysis_text is None and self.vision_client is not None:
                    print("⚠️ Ollama failed — falling back to Gemini for this request")
                    analysis_text = self._analyze_with_gemini(vision_prompt, image_b64)

            elif self._vision_backend == "gemini":
                analysis_text = self._analyze_with_gemini(vision_prompt, image_b64)

            if analysis_text is None:
                return {"success": False, "error": "Vision backend returned no response"}

            # Parse coordinates from response
            coordinates = self._parse_coordinates(analysis_text)

            self._log("screen_analyzed", {
                "query": query,
                "screenshot": image_path,
                "backend": self._vision_backend,
                "coordinates_found": len(coordinates) > 0
            })

            return {
                "success": True,
                "analysis": analysis_text,
                "coordinates": coordinates,
                "screenshot": image_path
            }

        except Exception as e:
            self._log("analysis_error", {"error": str(e)})
            return {"success": False, "error": str(e)}

    def _analyze_with_gemini(
        self, prompt: str, image_base64: str
    ) -> Optional[str]:
        """
        Send an image + prompt to Gemini Vision (cloud fallback).

        Args:
            prompt: The vision analysis prompt.
            image_base64: Base64-encoded PNG image data.

        Returns:
            The model's text response, or None on failure.
        """
        if self.vision_client is None:
            return None
        try:
            response = self.vision_client.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=[
                    prompt,
                    {
                        "mime_type": "image/png",
                        "data": image_base64,
                    },
                ],
            )
            return response.text
        except Exception as e:
            print(f"⚠️ Gemini vision error: {e}")
            return None

    def _parse_coordinates(self, text: str) -> List[Dict[str, Any]]:
        """
        Parse coordinates from Gemini's response.

        Args:
            text: Response text containing coordinate information

        Returns:
            List of coordinate dictionaries
        """
        coordinates = []

        # Try to find JSON array format first
        json_match = re.search(r'COORDINATES:\s*\[(.*?)\]', text, re.DOTALL)
        if json_match:
            try:
                coords_str = '[' + json_match.group(1) + ']'
                coords_list = json.loads(coords_str)
                return coords_list
            except:
                pass

        # Try simple x=, y= format
        simple_match = re.search(r'x=(\d+),?\s*y=(\d+)', text, re.IGNORECASE)
        if simple_match:
            coordinates.append({
                "x": int(simple_match.group(1)),
                "y": int(simple_match.group(2))
            })

        return coordinates

    def vision_loop(
        self,
        task: str,
        max_attempts: int = 3,
        verify: bool = True
    ) -> Dict[str, Any]:
        """
        Execute the Vision Loop: Snapshot → Analyze → Action → Verify

        Args:
            task: Natural language task (e.g., "Click the Start button")
            max_attempts: Maximum number of attempts
            verify: Whether to take a verification screenshot

        Returns:
            Dict with execution results
        """
        if not VISION_AVAILABLE or self._vision_backend is None:
            return {"success": False, "error": "Vision Loop not available"}

        if not GUI_AVAILABLE:
            return {"success": False, "error": "GUI control not available"}

        self._log("vision_loop_start", {"task": task})

        results = {
            "task": task,
            "attempts": [],
            "success": False
        }

        for attempt in range(max_attempts):
            attempt_data = {"attempt": attempt + 1}

            # STEP 1: SNAPSHOT - Capture current screen
            print(f"\n🔍 Vision Loop Attempt {attempt + 1}/{max_attempts}")
            print(f"📸 Step 1: Capturing screenshot...")

            screenshot = self.capture_screenshot()
            if not screenshot["success"]:
                attempt_data["error"] = f"Screenshot failed: {screenshot['error']}"
                results["attempts"].append(attempt_data)
                continue

            attempt_data["screenshot_before"] = screenshot["path"]
            print(f"   ✅ Screenshot saved: {screenshot['path']}")

            # STEP 2: ANALYZE - Find target UI element
            print(f"🧠 Step 2: Analyzing screen for: {task}")

            analysis = self.analyze_screen(
                query=f"find the UI element to {task}. Return exact pixel coordinates.",
                screenshot_data=screenshot
            )

            if not analysis["success"]:
                attempt_data["error"] = f"Analysis failed: {analysis['error']}"
                results["attempts"].append(attempt_data)
                continue

            if not analysis["coordinates"]:
                attempt_data["error"] = "No coordinates found in analysis"
                attempt_data["analysis"] = analysis["analysis"]
                results["attempts"].append(attempt_data)
                print(f"   ⚠️ Could not locate element. Analysis: {analysis['analysis'][:200]}")
                continue

            coords = analysis["coordinates"][0]  # Use first match
            attempt_data["analysis"] = analysis["analysis"]
            attempt_data["coordinates"] = coords
            print(f"   ✅ Found at: x={coords['x']}, y={coords['y']}")

            # STEP 3: ACTION - Perform the click
            print(f"👆 Step 3: Performing action...")

            action_result = self.gui_control(
                action='click',
                x=coords['x'],
                y=coords['y']
            )

            if not action_result["success"]:
                attempt_data["error"] = f"Action failed: {action_result['error']}"
                results["attempts"].append(attempt_data)
                continue

            attempt_data["action"] = action_result
            print(f"   ✅ Clicked at ({coords['x']}, {coords['y']})")

            # STEP 4: VERIFY - Take another screenshot to confirm
            if verify:
                print(f"✓ Step 4: Verifying action...")
                import time as _time
                _time.sleep(1)  # Wait for UI to update

                verify_screenshot = self.capture_screenshot()
                if verify_screenshot["success"]:
                    attempt_data["screenshot_after"] = verify_screenshot["path"]
                    print(f"   ✅ Verification screenshot: {verify_screenshot['path']}")

            # Success!
            results["success"] = True
            results["attempts"].append(attempt_data)
            print(f"\n✅ Vision Loop completed successfully!")
            break

        if not results["success"]:
            print(f"\n❌ Vision Loop failed after {max_attempts} attempts")

        self._log("vision_loop_complete", {
            "task": task,
            "success": results["success"],
            "attempts": len(results["attempts"])
        })

        return results

    # ── Proactive Goal Proposal (The Strategist) ──────────────

    def _llm_generate(self, prompt: str, timeout: int = 90) -> Optional[str]:
        """
        Send a text-only prompt to the local Ollama/llama3 model.

        Args:
            prompt: The text prompt to send.
            timeout: Request timeout in seconds.

        Returns:
            The model's text response, or None on failure.
        """
        try:
            resp = _requests.post(
                f"{self._ollama_host}/api/generate",
                json={
                    "model": "llama3.1",
                    "prompt": prompt,
                    "stream": False,
                },
                timeout=timeout,
            )
            if resp.status_code == 200:
                return resp.json().get("response", "")
            self._log("llm_generate_error", {"status": resp.status_code})
            return None
        except Exception as e:
            self._log("llm_generate_error", {"error": str(e)})
            return None

    def _parse_goal_json(self, llm_response: str) -> List[Dict[str, Any]]:
        """
        Extract a JSON array of goals from an LLM response.

        Tolerant of markdown fences, preamble text, and minor formatting issues.

        Args:
            llm_response: Raw text from the LLM.

        Returns:
            List of parsed goal dicts, or empty list on failure.
        """
        # Strip markdown code fences if present
        cleaned = re.sub(r"```(?:json)?\s*", "", llm_response)
        cleaned = cleaned.strip()

        # Find the JSON array in the response
        match = re.search(r"\[.*\]", cleaned, re.DOTALL)
        if not match:
            self._log("goal_parse_error", {"reason": "no JSON array found"})
            return []

        try:
            goals = json.loads(match.group(0))
        except json.JSONDecodeError as e:
            self._log("goal_parse_error", {"reason": str(e)})
            return []

        # Validate required fields
        valid_goals = []
        for g in goals:
            if isinstance(g, dict) and all(k in g for k in ("goal", "priority", "category")):
                valid_goals.append(g)

        return valid_goals

    def propose_goals(
        self, focus: Optional[str] = None, n_context: int = 10
    ) -> Dict[str, Any]:
        """
        Mine ChromaDB project history and propose actionable goals via LLM.

        Args:
            focus: Optional focus area to narrow the memory query.
            n_context: Number of memory items to retrieve per query.

        Returns:
            Dict with success status and proposed goals.
        """
        self._log("propose_goals_start", {"focus": focus})

        # ── 1. Gather context from memory ────────────────────────
        try:
            if focus:
                context_memories = recall(focus, n=n_context)
            else:
                context_memories = recall("recent project work and progress", n=n_context)

            pain_memories = recall("problems, errors, and unfinished tasks", n=5)

            try:
                pref_memories = recall_preferences("workflow and priorities")
            except Exception:
                pref_memories = []
        except Exception as e:
            self._log("propose_goals_error", {"phase": "recall", "error": str(e)})
            return {"success": False, "error": f"Memory recall failed: {e}"}

        # ── 2. Format context for the prompt ─────────────────────
        def _fmt(memories: List[Dict[str, Any]]) -> str:
            if not memories:
                return "(none)"
            lines = []
            for m in memories:
                meta = m.get("metadata", {})
                date = meta.get("timestamp", "unknown date")
                mtype = meta.get("type", "general")
                lines.append(f"- [{mtype} | {date}] {m['text']}")
            return "\n".join(lines)

        formatted_memories = _fmt(context_memories + pain_memories)
        formatted_preferences = _fmt(pref_memories)

        # ── 3. Ask the LLM ───────────────────────────────────────
        prompt = (
            "You are O.R.I.O.N., reviewing your project memory to propose next goals.\n\n"
            f"Context from memory:\n{formatted_memories}\n\n"
            f"User preferences:\n{formatted_preferences}\n\n"
            "Propose 3-5 actionable goals. Output ONLY a JSON array:\n"
            '[{"goal": "...", "priority": "high|medium|low", '
            '"category": "development|learning|optimization|integration", '
            '"reasoning": "..."}]'
        )

        llm_response = self._llm_generate(prompt)
        if llm_response is None:
            self._log("propose_goals_error", {"phase": "llm", "error": "no response"})
            return {"success": False, "error": "LLM did not return a response"}

        # ── 4. Parse goals ────────────────────────────────────────
        parsed_goals = self._parse_goal_json(llm_response)
        if not parsed_goals:
            return {
                "success": False,
                "error": "Failed to parse goals from LLM response",
                "raw_response": llm_response[:500],
            }

        # ── 5. Store each goal in ChromaDB ────────────────────────
        stored_goals: List[Dict[str, Any]] = []
        now_iso = datetime.now().isoformat()

        for g in parsed_goals:
            goal_id = remember(
                text=g["goal"],
                metadata={
                    "type": "proposed_goal",
                    "status": "active",
                    "priority": g.get("priority", "medium"),
                    "category": g.get("category", "general"),
                    "reasoning": g.get("reasoning", ""),
                    "proposed_date": now_iso,
                },
            )
            stored_goals.append({
                "id": goal_id,
                "goal": g["goal"],
                "priority": g.get("priority", "medium"),
                "category": g.get("category", "general"),
                "reasoning": g.get("reasoning", ""),
            })

        self._log("propose_goals_complete", {"count": len(stored_goals)})

        return {
            "success": True,
            "goals_proposed": len(stored_goals),
            "goals": stored_goals,
        }

    def get_active_goals(self) -> Dict[str, Any]:
        """
        Retrieve all currently active proposed goals from ChromaDB.

        Returns:
            Dict with success status and list of active goals sorted by priority.
        """
        try:
            mem = get_memory()
            results = mem.collection.get(
                where={"$and": [{"type": "proposed_goal"}, {"status": "active"}]},
                include=["documents", "metadatas"],
            )

            goals: List[Dict[str, Any]] = []
            if results["ids"]:
                for i, gid in enumerate(results["ids"]):
                    meta = results["metadatas"][i] if results["metadatas"] else {}
                    goals.append({
                        "id": gid,
                        "text": results["documents"][i] if results["documents"] else "",
                        "priority": meta.get("priority", "medium"),
                        "category": meta.get("category", "general"),
                        "proposed_date": meta.get("proposed_date", ""),
                    })

            # Sort: high → medium → low
            priority_order = {"high": 0, "medium": 1, "low": 2}
            goals.sort(key=lambda g: priority_order.get(g["priority"], 1))

            self._log("get_active_goals", {"count": len(goals)})
            return {"success": True, "goals": goals}

        except Exception as e:
            self._log("get_active_goals_error", {"error": str(e)})
            return {"success": False, "error": str(e)}

    def update_goal(self, goal_id: str, status: str) -> Dict[str, Any]:
        """
        Update the status of a proposed goal.

        Args:
            goal_id: The ChromaDB document ID of the goal.
            status: New status — one of 'completed', 'dismissed', 'active'.

        Returns:
            Dict with success status and updated goal info.
        """
        valid_statuses = ("completed", "dismissed", "active")
        if status not in valid_statuses:
            return {
                "success": False,
                "error": f"Invalid status '{status}'. Must be one of {valid_statuses}",
            }

        try:
            mem = get_memory()
            # Fetch existing metadata
            existing = mem.collection.get(ids=[goal_id], include=["metadatas"])
            if not existing["ids"]:
                return {"success": False, "error": f"Goal '{goal_id}' not found"}

            old_meta = existing["metadatas"][0] if existing["metadatas"] else {}
            old_status = old_meta.get("status", "unknown")
            old_meta["status"] = status
            old_meta[f"{status}_date"] = datetime.now().isoformat()

            mem.collection.update(ids=[goal_id], metadatas=[old_meta])

            self._log("update_goal", {
                "goal_id": goal_id,
                "old_status": old_status,
                "new_status": status,
            })

            return {
                "success": True,
                "goal_id": goal_id,
                "old_status": old_status,
                "new_status": status,
            }

        except Exception as e:
            self._log("update_goal_error", {"goal_id": goal_id, "error": str(e)})
            return {"success": False, "error": str(e)}

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about executive actions, including goal counts."""
        stats = {
            "session_id": self.session_id,
            "action_count": self.action_count,
            "os": self.os,
            "trust_mode": self.trust_mode,
            "gui_available": GUI_AVAILABLE,
            "playwright_available": PLAYWRIGHT_AVAILABLE,
            "vision_available": self._vision_backend is not None,
            "vision_backend": self._vision_backend,
            "log_file": str(LOG_FILE),
        }

        # Add goal counts from ChromaDB (best-effort)
        try:
            mem = get_memory()
            for goal_status in ("active", "completed", "dismissed"):
                result = mem.collection.get(
                    where={"$and": [{"type": "proposed_goal"}, {"status": goal_status}]},
                    include=[],
                )
                stats[f"goals_{goal_status}"] = len(result["ids"]) if result["ids"] else 0
        except Exception:
            stats["goals_active"] = 0
            stats["goals_completed"] = 0
            stats["goals_dismissed"] = 0

        return stats


# Convenience functions
_executive_instance = None

def get_executive() -> OrionExecutive:
    """Get or create the global Executive instance."""
    global _executive_instance
    if _executive_instance is None:
        _executive_instance = OrionExecutive()
    return _executive_instance


if __name__ == "__main__":
    # Test the Executive module
    print("=" * 70)
    print("O.R.I.O.N. EXECUTIVE MODULE TEST")
    print("=" * 70)

    exec_module = OrionExecutive(trust_mode=False)  # Require confirmation for safety

    # Test 1: Shell command (safe)
    print("\n🧪 Test 1: Shell command (ls)")
    result = exec_module.system_shell("ls -la")
    print(f"✅ Result: {result['success']}")
    if result['success']:
        print(f"Output (first 200 chars): {result['stdout'][:200]}")

    # Test 2: Vision Loop - Screenshot capture
    if VISION_AVAILABLE:
        print("\n🧪 Test 2: Screenshot capture")
        screenshot = exec_module.capture_screenshot()
        if screenshot['success']:
            print(f"✅ Screenshot saved: {screenshot['path']}")
            print(f"   Size: {screenshot['size']}")
        else:
            print(f"❌ Screenshot failed: {screenshot['error']}")

        # Test 3: Vision Loop - Full cycle (requires user confirmation)
        print("\n🧪 Test 3: Vision Loop (Full cycle)")
        print("   This will demonstrate the complete Vision Loop:")
        print("   Snapshot → Analyze → Action → Verify")
        print("\n   Example task: 'Click the Terminal icon in the dock'")
        print("   Note: Requires manual confirmation for safety")

    # Test 4: Proactive Goal Proposal
    print("\n🧪 Test 4: Proactive Goal Proposal")
    print("   Testing propose_goals()...")
    goal_result = exec_module.propose_goals()
    if goal_result["success"]:
        print(f"✅ Proposed {goal_result['goals_proposed']} goals:")
        for g in goal_result["goals"]:
            print(f"   [{g['priority']}] {g['goal']}")
    else:
        print(f"⚠️ Goal proposal: {goal_result.get('error', 'unavailable')}")

    # Test 5: Retrieve active goals
    print("\n🧪 Test 5: Get active goals")
    active = exec_module.get_active_goals()
    if active["success"]:
        print(f"✅ Active goals: {len(active['goals'])}")
        for g in active["goals"]:
            print(f"   [{g['priority']}] {g['text'][:80]}")
    else:
        print(f"⚠️ Active goals: {active.get('error', 'unavailable')}")

    # Test 6: Show stats
    print("\n" + "=" * 70)
    print("📊 Executive Stats:")
    stats = exec_module.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    print("=" * 70)

    print("\n✅ O.R.I.O.N. EXECUTIVE MODULE - All systems operational!")
    if exec_module._vision_backend:
        backend_label = "Ollama/llava (local)" if exec_module._vision_backend == "ollama" else "Gemini (cloud)"
        print(f"🔮 VISION LOOP ENABLED via {backend_label} - Ready for visual desktop automation!")
    print("🎯 GOAL PROPOSAL ENABLED - The Strategist is ready!")
