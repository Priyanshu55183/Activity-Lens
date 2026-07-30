"""
ActivityLens – Sessionizer
============================

Transforms a chronological list of raw snapshots into activity sessions.

What is a "session"?
    A contiguous period where the user was focused on the same window.
    Five snapshots of "main.py - Visual Studio Code" 5 seconds apart become
    one session: "VS Code for 25 seconds."

Algorithm:
    1. Walk snapshots chronologically.
    2. If the next snapshot matches the current session's (process_name, window_title),
       extend the session (increment snapshot_count, move end_time forward).
    3. If different, close the current session and start a new one.
    4. If the gap between two consecutive snapshots exceeds idle_threshold,
       insert an "[idle]" session covering that gap before starting the new session.
    5. The last session's duration = its accumulated span + one polling interval
       (since the last snapshot proves the user was still there for at least
       one more interval).

🎯 Interview-relevant: Pure function design
    sessionize() takes data in, returns data out. No database calls, no global
    state, no side effects. This makes it trivially testable — we feed it
    synthetic snapshot lists and assert on the output.  The pipeline module
    handles the DB read/write around it.
"""

from datetime import datetime, timezone


def _parse_ts(iso_str: str) -> datetime:
    """Parse an ISO 8601 timestamp string into a datetime object."""
    # Handle both 'Z' suffix and '+00:00' formats
    if iso_str.endswith("Z"):
        iso_str = iso_str[:-1] + "+00:00"
    return datetime.fromisoformat(iso_str)


def _session_key(snapshot: dict) -> tuple:
    """
    The grouping key for session merging.
    
    Two consecutive snapshots with the same key are part of the same session.
    We use (process_name, window_title) so that switching tabs/files within
    the same app creates a new session — this gives more granular tracking.
    """
    return (snapshot["process_name"], snapshot["window_title"])


def _make_idle_session(start_time: str, end_time: str, duration_seconds: float) -> dict:
    """Create an idle session dict for gaps exceeding the idle threshold."""
    return {
        "start_time": start_time,
        "end_time": end_time,
        "duration_seconds": duration_seconds,
        "process_name": "[idle]",
        "window_title": None,
        "is_browser": False,
        "page_title": None,
        "snapshot_count": 0,
    }


def sessionize(
    snapshots: list[dict],
    idle_threshold_seconds: int = 300,
    polling_interval_seconds: int = 5,
) -> list[dict]:
    """
    Merge a chronological list of raw snapshots into activity sessions.
    
    Args:
        snapshots: List of snapshot dicts (must be sorted by timestamp ASC).
                   Each dict must have: timestamp, process_name, window_title,
                   is_browser, page_title.
        idle_threshold_seconds: If the gap between two consecutive snapshots
                                exceeds this, an idle session is inserted.
        polling_interval_seconds: Used to estimate the duration of the last
                                  session (since we don't know when the user
                                  actually stopped).
    
    Returns:
        List of session dicts, each containing:
            start_time, end_time, duration_seconds, process_name,
            window_title, is_browser, page_title, snapshot_count
    
    🎯 Interview-relevant: Why not just GROUP BY?
        SQL GROUP BY can count snapshots per app, but it can't handle
        interleaved usage. If you use VS Code, then Chrome, then VS Code
        again, GROUP BY merges both VS Code periods into one. Sessionization
        preserves the timeline: VS Code session → Chrome session → VS Code session.
    """
    if not snapshots:
        return []

    sessions = []
    
    # Start the first session from the first snapshot
    current = {
        "start_time": snapshots[0]["timestamp"],
        "end_time": snapshots[0]["timestamp"],
        "process_name": snapshots[0]["process_name"],
        "window_title": snapshots[0]["window_title"],
        "is_browser": snapshots[0].get("is_browser", False),
        "page_title": snapshots[0].get("page_title"),
        "snapshot_count": 1,
    }

    for i in range(1, len(snapshots)):
        prev_snap = snapshots[i - 1]
        curr_snap = snapshots[i]

        prev_time = _parse_ts(prev_snap["timestamp"])
        curr_time = _parse_ts(curr_snap["timestamp"])
        gap_seconds = (curr_time - prev_time).total_seconds()

        # Check for idle gap
        if gap_seconds > idle_threshold_seconds:
            # Close the current session — its end is one polling interval
            # after the last snapshot in the session
            current_end = _parse_ts(current["end_time"])
            actual_end = current_end  # end at the last snapshot's time
            current["end_time"] = actual_end.isoformat()
            start = _parse_ts(current["start_time"])
            current["duration_seconds"] = (actual_end - start).total_seconds() + polling_interval_seconds
            sessions.append(current)

            # Insert idle session for the gap
            idle_start = actual_end.isoformat()
            idle_end = curr_snap["timestamp"]
            idle_duration = (_parse_ts(idle_end) - actual_end).total_seconds()
            sessions.append(_make_idle_session(idle_start, idle_end, idle_duration))

            # Start a new session from the current snapshot
            current = {
                "start_time": curr_snap["timestamp"],
                "end_time": curr_snap["timestamp"],
                "process_name": curr_snap["process_name"],
                "window_title": curr_snap["window_title"],
                "is_browser": curr_snap.get("is_browser", False),
                "page_title": curr_snap.get("page_title"),
                "snapshot_count": 1,
            }

        elif _session_key(curr_snap) == _session_key(prev_snap) and \
             _session_key(curr_snap) == _session_key(current):
            # Same window — extend current session
            current["end_time"] = curr_snap["timestamp"]
            current["snapshot_count"] += 1

        else:
            # Different window — close current, start new
            start = _parse_ts(current["start_time"])
            end = _parse_ts(current["end_time"])
            current["duration_seconds"] = (end - start).total_seconds() + polling_interval_seconds
            sessions.append(current)

            current = {
                "start_time": curr_snap["timestamp"],
                "end_time": curr_snap["timestamp"],
                "process_name": curr_snap["process_name"],
                "window_title": curr_snap["window_title"],
                "is_browser": curr_snap.get("is_browser", False),
                "page_title": curr_snap.get("page_title"),
                "snapshot_count": 1,
            }

    # Close the last session
    start = _parse_ts(current["start_time"])
    end = _parse_ts(current["end_time"])
    current["duration_seconds"] = (end - start).total_seconds() + polling_interval_seconds
    sessions.append(current)

    return sessions
