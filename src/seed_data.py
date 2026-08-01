"""
ActivityLens - Seed Data Generator
====================================

Generates realistic multi-day test data for demos and development.
Simulates a developer's typical workday with coding, browsing, meetings,
and idle gaps.

Usage:
    python src/seed_data.py              # Seed 7 days of data
    python src/seed_data.py --days 14    # Seed 14 days
    python src/seed_data.py --clear      # Clear existing data first
"""

import sys
import random
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import Config
from storage import init_db, insert_snapshot, insert_sessions
from sessionizer import sessionize
from classifier import classify_sessions


# ---------------------------------------------------------------------------
# Activity templates - realistic developer workday patterns
# ---------------------------------------------------------------------------

CODING_ACTIVITIES = [
    ("Code.exe", "main.py - Visual Studio Code"),
    ("Code.exe", "storage.py - Visual Studio Code"),
    ("Code.exe", "config.py - Visual Studio Code"),
    ("Code.exe", "capture.py - Visual Studio Code"),
    ("Code.exe", "sessionizer.py - Visual Studio Code"),
    ("Code.exe", "classifier.py - Visual Studio Code"),
    ("Code.exe", "pipeline.py - Visual Studio Code"),
    ("Code.exe", "test_capture.py - Visual Studio Code"),
    ("Code.exe", "server.py - Visual Studio Code"),
    ("Code.exe", "index.html - Visual Studio Code"),
]

PRODUCTIVE_BROWSING = [
    ("chrome.exe", "GitHub - Pull Request #42 - Google Chrome", True, "GitHub - Pull Request #42"),
    ("chrome.exe", "Stack Overflow - Python datetime - Google Chrome", True, "Stack Overflow - Python datetime"),
    ("chrome.exe", "Flask Documentation - Google Chrome", True, "Flask Documentation"),
    ("chrome.exe", "MDN Web Docs - CSS Grid - Google Chrome", True, "MDN Web Docs - CSS Grid"),
    ("chrome.exe", "GitHub - Issues - Google Chrome", True, "GitHub - Issues"),
    ("msedge.exe", "Python Docs - sqlite3 - Microsoft Edge", True, "Python Docs - sqlite3"),
    ("chrome.exe", "GitHub Actions - CI Pipeline - Google Chrome", True, "GitHub Actions - CI Pipeline"),
    ("chrome.exe", "API Reference - Chart.js - Google Chrome", True, "API Reference - Chart.js"),
]

DISTRACTING_BROWSING = [
    ("chrome.exe", "YouTube - Coding Music - Google Chrome", True, "YouTube - Coding Music"),
    ("chrome.exe", "Reddit - r/programming - Google Chrome", True, "Reddit - r/programming"),
    ("chrome.exe", "Twitter - Tech News - Google Chrome", True, "Twitter - Tech News"),
    ("chrome.exe", "YouTube - Conference Talk - Google Chrome", True, "YouTube - Conference Talk"),
    ("msedge.exe", "Reddit - r/python - Microsoft Edge", True, "Reddit - r/python"),
]

NEUTRAL_ACTIVITIES = [
    ("explorer.exe", "Activity-Lens"),
    ("explorer.exe", "Documents"),
    ("WindowsTerminal.exe", "PowerShell - npm run dev"),
    ("WindowsTerminal.exe", "PowerShell - pytest"),
    ("Slack.exe", "Slack - team-engineering"),
    ("ms-teams.exe", "Microsoft Teams - Daily Standup"),
    ("notepad.exe", "notes.txt - Notepad"),
    ("Outlook.exe", "Inbox - priya@company.com - Outlook"),
]

# Workday structure: (start_hour, end_hour, activity_weights)
# weights: (coding, prod_browse, distract_browse, neutral, idle_chance)
WORKDAY_BLOCKS = [
    (9, 10, (0.50, 0.15, 0.05, 0.25, 0.05)),   # Morning: ramp up
    (10, 12, (0.65, 0.15, 0.05, 0.10, 0.05)),   # Deep work
    (12, 13, (0.10, 0.05, 0.30, 0.40, 0.15)),   # Lunch break
    (13, 14, (0.40, 0.20, 0.10, 0.20, 0.10)),   # Post-lunch
    (14, 16, (0.60, 0.15, 0.05, 0.15, 0.05)),   # Afternoon deep work
    (16, 17, (0.35, 0.20, 0.15, 0.20, 0.10)),   # Wind down
    (17, 18, (0.20, 0.10, 0.25, 0.30, 0.15)),   # Late afternoon
]


def _get_block_weights(hour: int) -> tuple:
    """Get activity weights for a given hour."""
    for start_h, end_h, weights in WORKDAY_BLOCKS:
        if start_h <= hour < end_h:
            return weights
    return (0.3, 0.1, 0.1, 0.3, 0.2)  # default


def _pick_activity(weights: tuple) -> dict | None:
    """Pick a random activity based on weights. Returns None for idle."""
    coding_w, prod_w, distract_w, neutral_w, idle_w = weights
    roll = random.random()

    if roll < coding_w:
        proc, title = random.choice(CODING_ACTIVITIES)
        return {"process_name": proc, "window_title": title,
                "is_browser": False, "page_title": None}
    elif roll < coding_w + prod_w:
        proc, title, is_b, page = random.choice(PRODUCTIVE_BROWSING)
        return {"process_name": proc, "window_title": title,
                "is_browser": is_b, "page_title": page}
    elif roll < coding_w + prod_w + distract_w:
        proc, title, is_b, page = random.choice(DISTRACTING_BROWSING)
        return {"process_name": proc, "window_title": title,
                "is_browser": is_b, "page_title": page}
    elif roll < coding_w + prod_w + distract_w + neutral_w:
        proc, title = random.choice(NEUTRAL_ACTIVITIES)
        return {"process_name": proc, "window_title": title,
                "is_browser": False, "page_title": None}
    else:
        return None  # idle


def generate_day(date: datetime, polling_interval: int = 5) -> list[dict]:
    """Generate a day's worth of realistic snapshots."""
    snapshots = []
    work_start = date.replace(hour=9, minute=0, second=0, microsecond=0)
    work_end = date.replace(hour=18, minute=0, second=0, microsecond=0)

    current_time = work_start
    current_activity = None
    activity_duration = 0  # how many more snapshots to stay on this activity

    while current_time < work_end:
        hour = current_time.hour
        weights = _get_block_weights(hour)

        if activity_duration <= 0:
            # Pick new activity
            activity = _pick_activity(weights)

            if activity is None:
                # Idle gap: skip 2-15 minutes
                gap = random.randint(2, 15) * 60
                current_time += timedelta(seconds=gap)
                current_activity = None
                activity_duration = 0
                continue

            current_activity = activity
            # Stay on this activity for 1-20 minutes (12-240 snapshots at 5s)
            min_snaps = max(1, 60 // polling_interval)
            max_snaps = max(min_snaps + 1, (20 * 60) // polling_interval)
            activity_duration = random.randint(min_snaps, max_snaps)

        if current_activity:
            snapshot = {
                "timestamp": current_time.isoformat(),
                "process_name": current_activity["process_name"],
                "window_title": current_activity["window_title"],
                "is_browser": current_activity["is_browser"],
                "page_title": current_activity["page_title"],
            }
            snapshots.append(snapshot)

        activity_duration -= 1
        current_time += timedelta(seconds=polling_interval)

    return snapshots


def main():
    parser = argparse.ArgumentParser(description="Seed ActivityLens with demo data")
    parser.add_argument("--days", type=int, default=7, help="Number of days to seed (default: 7)")
    parser.add_argument("--clear", action="store_true", help="Clear existing data first")
    args = parser.parse_args()

    config = Config()
    conn = init_db(config.db_path)

    print("=" * 60)
    print("  ActivityLens - Seed Data Generator")
    print("=" * 60)

    if args.clear:
        conn.execute("DELETE FROM snapshots")
        conn.execute("DELETE FROM sessions")
        conn.commit()
        print("\n  Cleared existing data.")

    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    total_snapshots = 0
    total_sessions = 0

    for day_offset in range(args.days - 1, -1, -1):
        day = today - timedelta(days=day_offset)
        date_str = day.strftime("%Y-%m-%d")

        # Skip weekends for realism
        if day.weekday() >= 5:
            print(f"  {date_str}  (weekend - skipped)")
            continue

        # Generate snapshots
        snapshots = generate_day(day, config.polling_interval)

        if not snapshots:
            continue

        # Insert snapshots
        for snap in snapshots:
            insert_snapshot(conn, snap)

        # Run sessionization + classification
        sessions = sessionize(
            snapshots,
            idle_threshold_seconds=config.idle_threshold,
            polling_interval_seconds=config.polling_interval,
        )
        classified = classify_sessions(sessions, config.classification_rules)

        # Clear any existing sessions for this date, then insert
        conn.execute(
            "DELETE FROM sessions WHERE substr(start_time, 1, 10) = ?",
            (date_str,),
        )
        conn.commit()
        insert_sessions(conn, classified)

        total_snapshots += len(snapshots)
        total_sessions += len(classified)

        # Quick stats
        prod_secs = sum(s["duration_seconds"] for s in classified if s["category"] == "productive")
        total_secs = sum(s["duration_seconds"] for s in classified if s["category"] != "idle")
        prod_pct = (prod_secs / total_secs * 100) if total_secs > 0 else 0

        print(f"  {date_str}  {len(snapshots):>5} snapshots  "
              f"{len(classified):>3} sessions  "
              f"{prod_pct:4.0f}% productive")

    conn.close()

    print(f"\n  Done! Seeded {total_snapshots} snapshots, {total_sessions} sessions.")
    print(f"  Run 'python src/server.py' to view the dashboard.")
    print("=" * 60)


if __name__ == "__main__":
    main()
