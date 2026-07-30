"""
ActivityLens – Unit Tests for classifier.py
=============================================

Tests the productivity classification logic.

Uses synthetic session data with various combinations of process names
and browser page titles to verify classification rules.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from classifier import classify_session, classify_sessions


# ---------------------------------------------------------------------------
# Fixtures — test classification rules
# ---------------------------------------------------------------------------

@pytest.fixture
def rules():
    """Realistic classification rules matching config.yaml defaults."""
    return {
        "productive": {
            "processes": ["code.exe", "devenv.exe", "windowsterminal.exe",
                         "cmd.exe", "powershell.exe"],
            "browser_titles": ["*stackoverflow*", "*stack overflow*", "*github*", "*docs.*",
                              "*documentation*", "*api*"],
        },
        "distracting": {
            "processes": [],
            "browser_titles": ["*youtube*", "*reddit*", "*twitter*",
                              "*instagram*", "*facebook*", "*tiktok*"],
        },
    }


def _make_session(process_name, window_title="", is_browser=False, page_title=None):
    """Helper to create a minimal session dict for testing."""
    return {
        "start_time": "2026-07-30T08:00:00+00:00",
        "end_time": "2026-07-30T08:05:00+00:00",
        "duration_seconds": 300,
        "process_name": process_name,
        "window_title": window_title,
        "is_browser": is_browser,
        "page_title": page_title,
        "snapshot_count": 60,
    }


# ---------------------------------------------------------------------------
# Tests: Process name matching
# ---------------------------------------------------------------------------

class TestProcessMatching:
    """Test classification based on process name."""

    def test_productive_process(self, rules):
        """Code.exe should be classified as productive."""
        session = _make_session("Code.exe", "main.py - VS Code")
        assert classify_session(session, rules) == "productive"

    def test_productive_process_case_insensitive(self, rules):
        """Process matching should be case-insensitive."""
        session = _make_session("CODE.EXE", "main.py - VS Code")
        assert classify_session(session, rules) == "productive"

    def test_terminal_productive(self, rules):
        """WindowsTerminal.exe should be productive."""
        session = _make_session("WindowsTerminal.exe", "PowerShell")
        assert classify_session(session, rules) == "productive"

    def test_unknown_process_neutral(self, rules):
        """An unknown process should default to neutral."""
        session = _make_session("explorer.exe", "Documents")
        assert classify_session(session, rules) == "neutral"

    def test_notepad_neutral(self, rules):
        """Notepad (not in any list) should be neutral."""
        session = _make_session("notepad.exe", "Untitled - Notepad")
        assert classify_session(session, rules) == "neutral"


# ---------------------------------------------------------------------------
# Tests: Browser title matching
# ---------------------------------------------------------------------------

class TestBrowserTitleMatching:
    """Test classification based on browser page titles."""

    def test_productive_browser_github(self, rules):
        """GitHub in browser should be productive."""
        session = _make_session("chrome.exe", "GitHub - Chrome",
                               is_browser=True, page_title="GitHub")
        assert classify_session(session, rules) == "productive"

    def test_productive_browser_stackoverflow(self, rules):
        """Stack Overflow in browser should be productive."""
        session = _make_session("chrome.exe", "Stack Overflow - Chrome",
                               is_browser=True, page_title="Stack Overflow")
        assert classify_session(session, rules) == "productive"

    def test_distracting_browser_youtube(self, rules):
        """YouTube in browser should be distracting."""
        session = _make_session("chrome.exe", "YouTube - Chrome",
                               is_browser=True, page_title="YouTube")
        assert classify_session(session, rules) == "distracting"

    def test_distracting_browser_reddit(self, rules):
        """Reddit in browser should be distracting."""
        session = _make_session("firefox.exe", "Reddit — Firefox",
                               is_browser=True, page_title="Reddit")
        assert classify_session(session, rules) == "distracting"

    def test_neutral_browser(self, rules):
        """A browser page not matching any rule should be neutral."""
        session = _make_session("chrome.exe", "Google Search - Chrome",
                               is_browser=True, page_title="Google Search")
        assert classify_session(session, rules) == "neutral"

    def test_browser_title_case_insensitive(self, rules):
        """Browser title matching should be case-insensitive."""
        session = _make_session("chrome.exe", "GITHUB - Chrome",
                               is_browser=True, page_title="GITHUB")
        assert classify_session(session, rules) == "productive"


# ---------------------------------------------------------------------------
# Tests: Idle sessions
# ---------------------------------------------------------------------------

class TestIdleSessions:
    """Test that idle sessions get the special 'idle' category."""

    def test_idle_always_idle(self, rules):
        """[idle] sessions should always be classified as 'idle'."""
        session = _make_session("[idle]", None)
        assert classify_session(session, rules) == "idle"

    def test_idle_ignores_rules(self, rules):
        """Idle classification takes priority over any rules."""
        # Even if we somehow added [idle] to productive, it should still be "idle"
        session = _make_session("[idle]", None)
        assert classify_session(session, rules) == "idle"


# ---------------------------------------------------------------------------
# Tests: classify_sessions (batch)
# ---------------------------------------------------------------------------

class TestBatchClassification:
    """Test the batch classification function."""

    def test_classifies_all_sessions(self, rules):
        """All sessions in the list should get a category."""
        sessions = [
            _make_session("Code.exe", "main.py"),
            _make_session("chrome.exe", "YouTube - Chrome",
                         is_browser=True, page_title="YouTube"),
            _make_session("explorer.exe", "Documents"),
            _make_session("[idle]"),
        ]
        classified = classify_sessions(sessions, rules)

        assert len(classified) == 4
        assert classified[0]["category"] == "productive"
        assert classified[1]["category"] == "distracting"
        assert classified[2]["category"] == "neutral"
        assert classified[3]["category"] == "idle"

    def test_non_mutating(self, rules):
        """classify_sessions should not mutate the original sessions."""
        original = _make_session("Code.exe", "main.py")
        classified = classify_sessions([original], rules)

        # Original should not have a "category" key
        assert "category" not in original
        assert "category" in classified[0]

    def test_empty_input(self, rules):
        """Empty session list should return empty list."""
        assert classify_sessions([], rules) == []


# ---------------------------------------------------------------------------
# Tests: Priority / first-match-wins
# ---------------------------------------------------------------------------

class TestPriority:
    """Test that productive rules take priority over distracting."""

    def test_productive_wins_tie(self, rules):
        """If a process matches both productive and distracting, productive wins."""
        # Add Code.exe to distracting as well (weird but tests priority)
        rules_with_tie = {
            "productive": {"processes": ["code.exe"], "browser_titles": []},
            "distracting": {"processes": ["code.exe"], "browser_titles": []},
        }
        session = _make_session("Code.exe", "main.py")
        assert classify_session(session, rules_with_tie) == "productive"

    def test_process_match_before_browser_title(self, rules):
        """Process name match should take priority over browser title match."""
        # A browser whose process is in the productive list
        # should be productive even if its page title is distracting
        rules_custom = {
            "productive": {"processes": ["chrome.exe"], "browser_titles": []},
            "distracting": {"processes": [], "browser_titles": ["*youtube*"]},
        }
        session = _make_session("chrome.exe", "YouTube - Chrome",
                               is_browser=True, page_title="YouTube")
        # chrome.exe matches productive processes first → productive
        assert classify_session(session, rules_custom) == "productive"


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
