"""
ActivityLens – Unit Tests for sessionizer.py
==============================================

Tests the session merging and idle detection logic.

All tests use synthetic snapshot data — no database, no OS calls.
This is the advantage of the pure-function design: we feed in lists
and assert on the output.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sessionizer import sessionize


# ---------------------------------------------------------------------------
# Helpers — generate synthetic snapshots
# ---------------------------------------------------------------------------

def _make_snapshots(entries: list[tuple], start_time=None, interval=5):
    """
    Generate a list of snapshot dicts from compact tuples.
    
    Args:
        entries: List of (process_name, window_title, is_browser, page_title)
                 or just (process_name, window_title) for non-browser apps.
        start_time: Base timestamp (defaults to a fixed time for reproducibility).
        interval: Seconds between snapshots (default: 5).
    
    Returns:
        List of snapshot dicts, chronologically ordered.
    """
    if start_time is None:
        start_time = datetime(2026, 7, 30, 8, 0, 0, tzinfo=timezone.utc)
    
    snapshots = []
    for i, entry in enumerate(entries):
        ts = start_time + timedelta(seconds=i * interval)
        
        if len(entry) == 2:
            proc, title = entry
            is_browser, page_title = False, None
        else:
            proc, title, is_browser, page_title = entry
        
        snapshots.append({
            "timestamp": ts.isoformat(),
            "process_name": proc,
            "window_title": title,
            "is_browser": is_browser,
            "page_title": page_title,
        })
    
    return snapshots


# ---------------------------------------------------------------------------
# Tests: Basic session merging
# ---------------------------------------------------------------------------

class TestBasicMerging:
    """Test that consecutive identical snapshots merge into one session."""

    def test_single_snapshot(self):
        """One snapshot → one session with duration = polling_interval."""
        snaps = _make_snapshots([("Code.exe", "main.py - VS Code")])
        sessions = sessionize(snaps, polling_interval_seconds=5)
        
        assert len(sessions) == 1
        assert sessions[0]["process_name"] == "Code.exe"
        assert sessions[0]["snapshot_count"] == 1
        assert sessions[0]["duration_seconds"] == 5  # one polling interval

    def test_identical_snapshots_merge(self):
        """Five identical snapshots → one session."""
        snaps = _make_snapshots([
            ("Code.exe", "main.py - VS Code"),
            ("Code.exe", "main.py - VS Code"),
            ("Code.exe", "main.py - VS Code"),
            ("Code.exe", "main.py - VS Code"),
            ("Code.exe", "main.py - VS Code"),
        ])
        sessions = sessionize(snaps, polling_interval_seconds=5)
        
        assert len(sessions) == 1
        assert sessions[0]["snapshot_count"] == 5
        # Duration = (4 intervals × 5s) + 5s trailing = 25s
        assert sessions[0]["duration_seconds"] == 25

    def test_empty_input(self):
        """No snapshots → no sessions."""
        assert sessionize([]) == []


# ---------------------------------------------------------------------------
# Tests: Context switches
# ---------------------------------------------------------------------------

class TestContextSwitches:
    """Test that switching apps creates separate sessions."""

    def test_simple_switch(self):
        """VS Code → Chrome → 2 sessions."""
        snaps = _make_snapshots([
            ("Code.exe", "main.py - VS Code"),
            ("Code.exe", "main.py - VS Code"),
            ("chrome.exe", "GitHub - Chrome", True, "GitHub"),
            ("chrome.exe", "GitHub - Chrome", True, "GitHub"),
        ])
        sessions = sessionize(snaps, polling_interval_seconds=5)
        
        assert len(sessions) == 2
        assert sessions[0]["process_name"] == "Code.exe"
        assert sessions[0]["snapshot_count"] == 2
        assert sessions[1]["process_name"] == "chrome.exe"
        assert sessions[1]["snapshot_count"] == 2

    def test_back_and_forth(self):
        """VS Code → Chrome → VS Code → 3 sessions (not merged)."""
        snaps = _make_snapshots([
            ("Code.exe", "main.py - VS Code"),
            ("Code.exe", "main.py - VS Code"),
            ("chrome.exe", "GitHub - Chrome", True, "GitHub"),
            ("Code.exe", "main.py - VS Code"),
            ("Code.exe", "main.py - VS Code"),
        ])
        sessions = sessionize(snaps, polling_interval_seconds=5)
        
        assert len(sessions) == 3
        assert sessions[0]["process_name"] == "Code.exe"
        assert sessions[1]["process_name"] == "chrome.exe"
        assert sessions[2]["process_name"] == "Code.exe"

    def test_same_app_different_file(self):
        """Switching files in VS Code creates separate sessions."""
        snaps = _make_snapshots([
            ("Code.exe", "main.py - VS Code"),
            ("Code.exe", "main.py - VS Code"),
            ("Code.exe", "storage.py - VS Code"),
            ("Code.exe", "storage.py - VS Code"),
        ])
        sessions = sessionize(snaps, polling_interval_seconds=5)
        
        assert len(sessions) == 2
        assert sessions[0]["window_title"] == "main.py - VS Code"
        assert sessions[1]["window_title"] == "storage.py - VS Code"


# ---------------------------------------------------------------------------
# Tests: Idle detection
# ---------------------------------------------------------------------------

class TestIdleDetection:
    """Test that gaps exceeding the idle threshold produce idle sessions."""

    def test_idle_gap_inserts_idle_session(self):
        """A 10-minute gap with 5-minute threshold → idle session inserted."""
        start = datetime(2026, 7, 30, 8, 0, 0, tzinfo=timezone.utc)
        
        snaps = [
            {
                "timestamp": start.isoformat(),
                "process_name": "Code.exe",
                "window_title": "main.py",
                "is_browser": False,
                "page_title": None,
            },
            {
                "timestamp": (start + timedelta(seconds=5)).isoformat(),
                "process_name": "Code.exe",
                "window_title": "main.py",
                "is_browser": False,
                "page_title": None,
            },
            {
                # 10-minute gap here
                "timestamp": (start + timedelta(minutes=10, seconds=5)).isoformat(),
                "process_name": "chrome.exe",
                "window_title": "Google - Chrome",
                "is_browser": True,
                "page_title": "Google",
            },
        ]
        
        sessions = sessionize(snaps, idle_threshold_seconds=300, polling_interval_seconds=5)
        
        # Should be: Code session, idle session, Chrome session
        assert len(sessions) == 3
        assert sessions[0]["process_name"] == "Code.exe"
        assert sessions[1]["process_name"] == "[idle]"
        assert sessions[2]["process_name"] == "chrome.exe"
        
        # Idle session should cover the gap
        assert sessions[1]["snapshot_count"] == 0

    def test_no_idle_within_threshold(self):
        """A gap within the threshold does NOT create an idle session."""
        start = datetime(2026, 7, 30, 8, 0, 0, tzinfo=timezone.utc)
        
        snaps = [
            {
                "timestamp": start.isoformat(),
                "process_name": "Code.exe",
                "window_title": "main.py",
                "is_browser": False,
                "page_title": None,
            },
            {
                # 4-minute gap (under 5-minute threshold)
                "timestamp": (start + timedelta(minutes=4)).isoformat(),
                "process_name": "chrome.exe",
                "window_title": "Google - Chrome",
                "is_browser": True,
                "page_title": "Google",
            },
        ]
        
        sessions = sessionize(snaps, idle_threshold_seconds=300, polling_interval_seconds=5)
        
        # No idle session — just Code → Chrome
        assert len(sessions) == 2
        assert sessions[0]["process_name"] == "Code.exe"
        assert sessions[1]["process_name"] == "chrome.exe"


# ---------------------------------------------------------------------------
# Tests: Browser sessions
# ---------------------------------------------------------------------------

class TestBrowserSessions:
    """Test that browser metadata is correctly propagated."""

    def test_browser_metadata_preserved(self):
        """Browser sessions should have is_browser=True and page_title set."""
        snaps = _make_snapshots([
            ("chrome.exe", "GitHub - Google Chrome", True, "GitHub"),
            ("chrome.exe", "GitHub - Google Chrome", True, "GitHub"),
        ])
        sessions = sessionize(snaps, polling_interval_seconds=5)
        
        assert len(sessions) == 1
        assert sessions[0]["is_browser"] is True
        assert sessions[0]["page_title"] == "GitHub"

    def test_different_browser_tabs_separate_sessions(self):
        """Switching browser tabs creates separate sessions."""
        snaps = _make_snapshots([
            ("chrome.exe", "GitHub - Chrome", True, "GitHub"),
            ("chrome.exe", "YouTube - Chrome", True, "YouTube"),
        ])
        sessions = sessionize(snaps, polling_interval_seconds=5)
        
        assert len(sessions) == 2
        assert sessions[0]["page_title"] == "GitHub"
        assert sessions[1]["page_title"] == "YouTube"


# ---------------------------------------------------------------------------
# Tests: Duration calculation
# ---------------------------------------------------------------------------

class TestDuration:
    """Test that session durations are calculated correctly."""

    def test_duration_single_snapshot(self):
        """Single snapshot duration = polling_interval."""
        snaps = _make_snapshots([("Code.exe", "main.py")])
        sessions = sessionize(snaps, polling_interval_seconds=5)
        assert sessions[0]["duration_seconds"] == 5

    def test_duration_multiple_snapshots(self):
        """Duration = time span + polling interval."""
        snaps = _make_snapshots([
            ("Code.exe", "main.py"),
            ("Code.exe", "main.py"),
            ("Code.exe", "main.py"),
        ], interval=10)
        sessions = sessionize(snaps, polling_interval_seconds=10)
        # Span = 20s (from first to last), + 10s trailing = 30s
        assert sessions[0]["duration_seconds"] == 30

    def test_duration_with_custom_interval(self):
        """Custom polling interval should be respected."""
        snaps = _make_snapshots([("Code.exe", "main.py")], interval=15)
        sessions = sessionize(snaps, polling_interval_seconds=15)
        assert sessions[0]["duration_seconds"] == 15


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
