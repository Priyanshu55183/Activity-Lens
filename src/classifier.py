"""
ActivityLens – Activity Classifier
====================================

Labels each session with a productivity category: productive, neutral, or distracting.

Classification rules:
    1. Idle sessions → "idle" (special category, always applied first)
    2. Process name exact match (case-insensitive)
    3. Process name glob pattern match (e.g., "pycharm*")
    4. Browser page title glob pattern match (for browser sessions)
    5. Default fallback → "neutral"

First match wins — so if Code.exe is in both productive and distracting lists
(which would be weird but possible), it gets "productive" because that's
checked first.

🎯 Interview-relevant: Separation of concerns
    The classifier doesn't know about the database or the sessionizer.
    It receives a list of sessions and returns them with a "category" field.
    The rules come from config.yaml via the Config object, but the classifier
    itself just takes a rules dict — making it easy to test with custom rules.
"""

from fnmatch import fnmatch


def classify_session(session: dict, rules: dict) -> str:
    """
    Classify a single session and return its category string.
    
    Args:
        session: A session dict with at least process_name, is_browser, page_title.
        rules: Classification rules dict with structure:
            {
                "productive": {"processes": [...], "browser_titles": [...]},
                "distracting": {"processes": [...], "browser_titles": [...]},
            }
    
    Returns:
        One of: "productive", "neutral", "distracting", "idle"
    """
    proc = session["process_name"]

    # Rule 0: idle sessions are always "idle"
    if proc == "[idle]":
        return "idle"

    proc_lower = proc.lower()

    # Check productive rules first (productive wins ties)
    for category in ["productive", "distracting"]:
        cat_rules = rules.get(category, {})

        # Rule 1: Process name match (exact or glob)
        for pattern in cat_rules.get("processes", []):
            if fnmatch(proc_lower, pattern.lower()):
                return category

        # Rule 2: Browser page title match (only for browser sessions)
        if session.get("is_browser") and session.get("page_title"):
            page_lower = session["page_title"].lower()
            for pattern in cat_rules.get("browser_titles", []):
                if fnmatch(page_lower, pattern.lower()):
                    return category

    # Default: neutral
    return "neutral"


def classify_sessions(sessions: list[dict], rules: dict) -> list[dict]:
    """
    Classify a list of sessions, adding a "category" field to each.
    
    This is a non-mutating function — it returns new dicts with the
    category added, leaving the originals unchanged.
    
    Args:
        sessions: List of session dicts from the sessionizer.
        rules: Classification rules dict (from Config.classification_rules).
    
    Returns:
        List of session dicts, each with an added "category" field.
    """
    classified = []
    for session in sessions:
        enriched = {**session, "category": classify_session(session, rules)}
        classified.append(enriched)
    return classified
