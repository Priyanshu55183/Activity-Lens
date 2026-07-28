"""
ActivityLens – Active Window Capture
=====================================

Core capture logic:  poll the OS for the currently-focused window, check it
against the privacy blocklist, extract browser page titles when applicable,
and return a clean snapshot dict ready for storage.

Design choice — polling vs. event-driven:
    We poll at a fixed interval (default 5s) rather than hooking into
    SetWinEventHook.  Polling is:
      • Simpler to implement and debug
      • Doesn't require running a Windows message loop
      • At 5s intervals, CPU cost is negligible (~0.01% of a core)
    The trade-off is we might miss very fast switches (< 5s), but those
    are exactly the "flickers" we'd merge away in sessionization anyway.

Design choice — window title parsing for browser info:
    Browsers put the page title in the window title bar:
      Chrome:  "GitHub - Google Chrome"
      Edge:    "Google - Microsoft Edge"
      Firefox: "Reddit — Mozilla Firefox"
    We split on the last " - " or " — " to extract the page title.
    This is zero-dependency and gives us the page title (more useful than
    a raw URL for understanding activity).  We can upgrade to UI Automation
    or a browser extension later if we need the actual URL.
"""

import re
import time
from datetime import datetime, timezone
from fnmatch import fnmatch

import psutil

# Win32 imports — these only work on Windows
import win32gui
import win32process

from config import Config


# ---------------------------------------------------------------------------
# Known browser process names → display names
# ---------------------------------------------------------------------------
KNOWN_BROWSERS = {
    "chrome.exe": "Google Chrome",
    "msedge.exe": "Microsoft Edge",
    "firefox.exe": "Mozilla Firefox",
    "brave.exe": "Brave Browser",
    "opera.exe": "Opera",
    "vivaldi.exe": "Vivaldi",
    "arc.exe": "Arc",
}

# Separators browsers use between page title and browser name.
# Chrome/Edge use " - ", Firefox uses " — " (em dash), some use " – " (en dash).
_BROWSER_TITLE_SEPARATORS = [" - ", " — ", " – "]


# ---------------------------------------------------------------------------
# 1. get_active_window()
# ---------------------------------------------------------------------------

def get_active_window() -> dict | None:
    """
    Query the OS for the currently focused window.
    
    Returns a dict with:
        - window_title (str): full title bar text
        - process_name (str): e.g. "chrome.exe"
        - process_id (int): PID
    
    Returns None if:
        - No window is focused (desktop, lock screen)
        - The window title is empty (system tray popups, etc.)
        - We can't access the process info (system processes)
    
    🎯 Interview-relevant: Win32 API call chain
        GetForegroundWindow → hwnd (window handle)
        GetWindowText(hwnd) → title string
        GetWindowThreadProcessId(hwnd) → (thread_id, pid)
        psutil.Process(pid).name() → "chrome.exe"
        
        This is the standard pattern for window introspection on Windows.
        The alternative (SetWinEventHook) is event-driven but requires
        running a message pump and is significantly more complex.
    """
    try:
        # Step 1: Get the handle to the foreground (active) window
        hwnd = win32gui.GetForegroundWindow()
        
        if not hwnd:
            return None

        # Step 2: Get the window title
        window_title = win32gui.GetWindowText(hwnd)
        
        if not window_title or not window_title.strip():
            return None

        # Step 3: Map window handle → PID → process name
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        
        try:
            process = psutil.Process(pid)
            process_name = process.name()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            # System processes or processes that exited between our two calls
            process_name = "Unknown"

        return {
            "window_title": window_title.strip(),
            "process_name": process_name,
            "process_id": pid,
        }

    except Exception:
        # Broad catch for any Win32 errors (e.g. during screen lock transitions)
        return None


# ---------------------------------------------------------------------------
# 2. is_blocked()
# ---------------------------------------------------------------------------

def is_blocked(process_name: str, window_title: str, config: Config) -> bool:
    """
    Check if a captured window should be dropped per the privacy blocklist.
    
    Two types of checks:
      1. Exact process name match (case-insensitive):
         "1Password.exe" blocks any window from 1Password.
      2. Glob pattern on window title (case-insensitive):
         "*bank*" blocks any window whose title contains "bank".
    
    🎯 Interview-relevant: Privacy at capture time
        Blocked data never touches the database — it's not "captured then
        deleted" but truly never written.  This is defense-in-depth: even
        if the DB is compromised, blocked app data was never there.
        
        The alternative (capture everything, filter on read) is weaker
        because the sensitive data still exists on disk.
    """
    # Check 1: exact process name match
    if process_name.lower() in config.blocklist_processes:
        return True

    # Check 2: glob pattern match on title
    title_lower = window_title.lower()
    for pattern in config.blocklist_title_patterns:
        if fnmatch(title_lower, pattern):
            return True

    return False


# ---------------------------------------------------------------------------
# 3. extract_browser_info()
# ---------------------------------------------------------------------------

def extract_browser_info(process_name: str, window_title: str) -> dict:
    """
    If the active window is a known browser, extract the page title from
    the window title bar.
    
    Browser window titles follow the pattern:
        "Page Title - Browser Name"
        "Page Title — Browser Name"   (Firefox uses em dash)
    
    We split on the LAST separator to handle page titles that themselves
    contain dashes (e.g. "my-project - Issues - Google Chrome" → 
    page_title = "my-project - Issues").
    
    Returns:
        {"is_browser": True, "page_title": "..."}  — if browser detected
        {"is_browser": False, "page_title": None}   — otherwise
    """
    proc_lower = process_name.lower()

    if proc_lower not in KNOWN_BROWSERS:
        return {"is_browser": False, "page_title": None}

    # Try each separator, find the last occurrence
    page_title = window_title  # fallback: use full title

    for sep in _BROWSER_TITLE_SEPARATORS:
        idx = window_title.rfind(sep)
        if idx > 0:
            page_title = window_title[:idx].strip()
            break

    return {"is_browser": True, "page_title": page_title}


# ---------------------------------------------------------------------------
# 4. capture_snapshot()
# ---------------------------------------------------------------------------

def capture_snapshot(config: Config) -> dict | None:
    """
    Orchestrator: capture one complete snapshot of the current activity.
    
    Flow:
        get_active_window()  →  is_blocked()  →  extract_browser_info()
        
    Returns a flat dict ready for SQLite insertion, or None if:
        - No window is focused
        - The window is on the blocklist
    
    The timestamp is captured at call time in UTC ISO 8601 format.
    """
    # Step 1: Get raw window info
    window_info = get_active_window()
    if window_info is None:
        return None

    # Step 2: Privacy check — blocked apps never reach storage
    if is_blocked(window_info["process_name"], window_info["window_title"], config):
        return None

    # Step 3: Extract browser page title if applicable
    browser_info = extract_browser_info(
        window_info["process_name"], window_info["window_title"]
    )

    # Step 4: Build the snapshot
    snapshot = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "process_name": window_info["process_name"],
        "window_title": window_info["window_title"],
        "is_browser": browser_info["is_browser"],
        "page_title": browser_info["page_title"],
    }

    return snapshot
