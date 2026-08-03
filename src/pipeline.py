"""
ActivityLens – Processing Pipeline
====================================

Orchestrates the full Day 2 flow:
    raw snapshots → sessionize → classify → store in sessions table

This keeps report.py thin (just formatting) and makes the processing logic
reusable for Day 3's dashboard.

Usage (as a module):
    from pipeline import run_pipeline
    sessions = run_pipeline(conn, config)           # today
    sessions = run_pipeline(conn, config, "2026-07-29")  # specific date
"""

import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import Config
from storage import (
    init_db,
    get_snapshots_for_date,
    insert_sessions,
    get_sessions_for_date,
    insert_browsing_history,
)
from sessionizer import sessionize
from classifier import classify_sessions


def run_pipeline(
    conn,
    config: Config,
    date_str: str | None = None,
    force: bool = False,
) -> list[dict]:
    """
    Run the full processing pipeline for a given date.
    
    Steps:
        1. Query raw snapshots for the target date
        2. Sessionize → merge into activity sessions
        3. Classify → label each session
        4. Store sessions in the sessions table
        5. Return the processed sessions
    
    Args:
        conn: SQLite connection (from init_db).
        config: Config object with idle_threshold and classification_rules.
        date_str: Target date in YYYY-MM-DD format. Defaults to today (UTC).
        force: If True, re-process even if sessions already exist for this date.
               Existing sessions for the date will be deleted and re-created.
    
    Returns:
        List of classified session dicts.
    
    🎯 Interview-relevant: Idempotency
        By default, if sessions already exist for a date, we return them
        from the DB rather than re-processing.  The --raw / force flag
        lets you re-process (e.g. after changing classification rules).
        This avoids duplicate sessions from running the pipeline twice.
    """
    if date_str is None:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Check if sessions already exist for this date
    if not force:
        existing = get_sessions_for_date(conn, date_str)
        if existing:
            return existing

    # Step 1: Fetch raw snapshots
    snapshots = get_snapshots_for_date(conn, date_str)
    
    if not snapshots:
        return []

    # Step 2: Sessionize
    sessions = sessionize(
        snapshots,
        idle_threshold_seconds=config.idle_threshold,
        polling_interval_seconds=config.polling_interval,
    )

    # Step 3: Classify
    classified = classify_sessions(sessions, config.classification_rules)

    # Step 4: Store (delete old sessions for this date first if force=True)
    if force:
        conn.execute(
            "DELETE FROM sessions WHERE substr(start_time, 1, 10) = ?",
            (date_str,),
        )
        conn.commit()

    insert_sessions(conn, classified)

    # Step 5: Populate browsing history (aggregated browser visits)
    insert_browsing_history(conn, classified, date_str)

    return classified


# ---------------------------------------------------------------------------
# CLI entry point — useful for testing the pipeline directly
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    config = Config()
    conn = init_db(config.db_path)

    date_str = None
    force = "--force" in sys.argv or "--raw" in sys.argv

    # Check for --date argument
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--date" and i + 1 < len(sys.argv):
            date_str = sys.argv[i + 1]

    print("=" * 60)
    print("  ActivityLens — Processing Pipeline")
    print("=" * 60)

    if date_str:
        print(f"\n  Target date: {date_str}")
    else:
        print(f"\n  Target date: today (UTC)")

    if force:
        print("  Mode: force re-process")

    sessions = run_pipeline(conn, config, date_str=date_str, force=force)

    print(f"\n  Result: {len(sessions)} sessions")
    for s in sessions:
        cat = s.get("category", "?")
        dur = s.get("duration_seconds", 0)
        mins = dur / 60
        proc = s["process_name"]
        print(f"    [{cat:>12}]  {mins:5.1f}m  {proc}")

    conn.close()
    print("\n" + "=" * 60)
