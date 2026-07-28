"""
ActivityLens – Unit Tests for capture.py
=========================================

Tests the pure functions in capture.py that don't require a live OS:
    - is_blocked() — privacy blocklist enforcement
    - extract_browser_info() — browser page title extraction

We don't test get_active_window() or capture_snapshot() here because they
depend on the actual Windows desktop state.  Those are tested manually
by running main.py.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Add src/ to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from capture import is_blocked, extract_browser_info


# ---------------------------------------------------------------------------
# Fixtures — mock Config objects for testing
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_config():
    """Config with a realistic blocklist."""
    config = MagicMock()
    config.blocklist_processes = ["1password.exe", "keepass.exe", "bitwarden.exe"]
    config.blocklist_title_patterns = ["*bank*", "*health*", "*medical*", "*password*"]
    return config


@pytest.fixture
def empty_config():
    """Config with no blocklist (nothing is blocked)."""
    config = MagicMock()
    config.blocklist_processes = []
    config.blocklist_title_patterns = []
    return config


# ---------------------------------------------------------------------------
# Tests: is_blocked()
# ---------------------------------------------------------------------------

class TestIsBlocked:
    """Test the privacy blocklist logic."""

    def test_blocked_process_exact_match(self, mock_config):
        """A blocklisted process name should be blocked."""
        assert is_blocked("1Password.exe", "Main Window", mock_config) is True

    def test_blocked_process_case_insensitive(self, mock_config):
        """Process name matching should be case-insensitive."""
        assert is_blocked("KEEPASS.EXE", "Passwords", mock_config) is True
        assert is_blocked("keepass.exe", "Passwords", mock_config) is True

    def test_allowed_process(self, mock_config):
        """A non-blocklisted process should be allowed."""
        assert is_blocked("Code.exe", "main.py - VS Code", mock_config) is False

    def test_blocked_title_pattern(self, mock_config):
        """A window title matching a glob pattern should be blocked."""
        assert is_blocked("chrome.exe", "My Bank Account - Chrome", mock_config) is True

    def test_blocked_title_pattern_case_insensitive(self, mock_config):
        """Title pattern matching should be case-insensitive."""
        assert is_blocked("chrome.exe", "HEALTH RECORDS - Chrome", mock_config) is True

    def test_allowed_title(self, mock_config):
        """A non-matching title should be allowed."""
        assert is_blocked("chrome.exe", "GitHub - Google Chrome", mock_config) is False

    def test_empty_blocklist_allows_everything(self, empty_config):
        """With no blocklist, nothing should be blocked."""
        assert is_blocked("1Password.exe", "My Bank", empty_config) is False

    def test_blocked_title_partial_match(self, mock_config):
        """Glob pattern *bank* should match 'bank' anywhere in the title."""
        assert is_blocked("msedge.exe", "Online Banking Portal - Edge", mock_config) is True
        assert is_blocked("firefox.exe", "bankofamerica.com", mock_config) is True

    def test_password_in_title_blocked(self, mock_config):
        """Title containing 'password' should be blocked."""
        assert is_blocked("chrome.exe", "Reset Password - Chrome", mock_config) is True


# ---------------------------------------------------------------------------
# Tests: extract_browser_info()
# ---------------------------------------------------------------------------

class TestExtractBrowserInfo:
    """Test browser detection and page title extraction."""

    def test_chrome_standard_title(self):
        """Chrome: 'Page Title - Google Chrome' → page_title = 'Page Title'."""
        result = extract_browser_info("chrome.exe", "GitHub - Google Chrome")
        assert result["is_browser"] is True
        assert result["page_title"] == "GitHub"

    def test_edge_standard_title(self):
        """Edge: 'Page Title - Microsoft Edge'."""
        result = extract_browser_info("msedge.exe", "Google Search - Microsoft Edge")
        assert result["is_browser"] is True
        assert result["page_title"] == "Google Search"

    def test_firefox_em_dash(self):
        """Firefox uses em dash: 'Page Title — Mozilla Firefox'."""
        result = extract_browser_info("firefox.exe", "Reddit — Mozilla Firefox")
        assert result["is_browser"] is True
        assert result["page_title"] == "Reddit"

    def test_title_with_dashes(self):
        """Page titles containing dashes should keep them (split on LAST separator)."""
        result = extract_browser_info(
            "chrome.exe", 
            "my-project - Issues · GitHub - Google Chrome"
        )
        assert result["is_browser"] is True
        assert result["page_title"] == "my-project - Issues · GitHub"

    def test_non_browser_process(self):
        """Non-browser processes should return is_browser=False."""
        result = extract_browser_info("Code.exe", "main.py - VS Code")
        assert result["is_browser"] is False
        assert result["page_title"] is None

    def test_brave_browser(self):
        """Brave should be recognized as a browser."""
        result = extract_browser_info("brave.exe", "YouTube - Brave")
        assert result["is_browser"] is True
        assert result["page_title"] == "YouTube"

    def test_browser_no_separator(self):
        """If no separator found, fallback to full title."""
        result = extract_browser_info("chrome.exe", "New Tab")
        assert result["is_browser"] is True
        assert result["page_title"] == "New Tab"

    def test_browser_case_insensitive(self):
        """Process name matching should be case-insensitive."""
        result = extract_browser_info("Chrome.exe", "Test - Google Chrome")
        # Chrome.exe (capital C) won't match "chrome.exe" in KNOWN_BROWSERS
        # because we do proc_lower = process_name.lower()
        assert result["is_browser"] is True
        assert result["page_title"] == "Test"


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
