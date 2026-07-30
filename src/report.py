"""
ActivityLens - Daily Activity Report
======================================

Human-readable daily summary of your activity. This is the primary
user-facing output of Day 2.

Usage:
    python src/report.py                        # Today's report
    python src/report.py --date 2026-07-30      # Specific date
    python src/report.py --raw                   # Force re-sessionize from raw snapshots

Output:
    - Time breakdown by category (productive / neutral / distracting / idle)
    - Top activities ranked by duration
    - Session timeline showing the sequence of activities
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import Config
from storage import init_db
from pipeline import run_pipeline


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _format_duration(seconds: float) -> str:
    """Format seconds into a human-readable string like '2h 15m' or '43m'."""
    if seconds < 0:
        return "0m"

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)

    if hours > 0:
        return f"{hours}h {minutes:02d}m"
    return f"{minutes}m"


def _format_time(iso_str: str) -> str:
    """Extract HH:MM from an ISO timestamp."""
    return iso_str[11:16]


def _pct(part: float, total: float) -> str:
    """Format as percentage string, handling division by zero."""
    if total <= 0:
        return "  0%"
    return f"{(part / total) * 100:3.0f}%"


# ---------------------------------------------------------------------------
# Report sections
# ---------------------------------------------------------------------------

def print_summary(sessions: list[dict]):
    """Print the time breakdown by category."""
    totals = {}
    for s in sessions:
        cat = s.get("category", "neutral")
        totals[cat] = totals.get(cat, 0) + s["duration_seconds"]

    idle_seconds = totals.pop("idle", 0)
    active_seconds = sum(totals.values())
    total_seconds = active_seconds + idle_seconds

    print("\n  Summary")
    print("  " + "-" * 40)
    print(f"    Total tracked time:   {_format_duration(total_seconds)}")
    print()

    # Show categories in order: productive → neutral → distracting
    for cat in ["productive", "neutral", "distracting"]:
        secs = totals.get(cat, 0)
        bar = "#" * max(1, int((secs / max(active_seconds, 1)) * 20)) if secs > 0 else ""
        print(f"    {cat.capitalize():<14}  {_format_duration(secs):>8}  "
              f"({_pct(secs, active_seconds)})  {bar}")

    if idle_seconds > 0:
        print(f"    {'Idle':<14}  {_format_duration(idle_seconds):>8}")


def print_top_activities(sessions: list[dict], limit: int = 10):
    """Print the top activities by total duration."""
    # Aggregate by (process_name, page_title or window_title)
    activity_totals = {}
    for s in sessions:
        if s["process_name"] == "[idle]":
            continue

        if s.get("is_browser") and s.get("page_title"):
            key = (s["process_name"], s["page_title"], s.get("category", "neutral"))
        else:
            # For non-browser, group by process name only for cleaner output
            key = (s["process_name"], None, s.get("category", "neutral"))

        activity_totals[key] = activity_totals.get(key, 0) + s["duration_seconds"]

    # Sort by duration descending
    ranked = sorted(activity_totals.items(), key=lambda x: x[1], reverse=True)

    print(f"\n  Top Activities")
    print("  " + "-" * 40)

    for i, ((proc, detail, cat), secs) in enumerate(ranked[:limit], 1):
        if detail:
            label = f"{proc} ({detail})"
        else:
            label = proc

        # Truncate long labels
        if len(label) > 35:
            label = label[:32] + "..."

        cat_tag = f"[{cat}]"
        print(f"    {i:>2}.  {label:<36} {_format_duration(secs):>7}  {cat_tag}")


def print_timeline(sessions: list[dict], limit: int = 15):
    """Print a chronological timeline of sessions."""
    # Filter out very short sessions (<10s) for cleaner output
    significant = [s for s in sessions if s["duration_seconds"] >= 10]

    if not significant:
        print("\n  No significant sessions to display.")
        return

    display = significant[-limit:]  # Show most recent
    if len(significant) > limit:
        print(f"\n  Session Timeline (last {limit} of {len(significant)})")
    else:
        print(f"\n  Session Timeline ({len(significant)} sessions)")

    print("  " + "-" * 40)

    for s in display:
        start = _format_time(s["start_time"])
        end = _format_time(s["end_time"])
        proc = s["process_name"]
        cat = s.get("category", "neutral")

        if proc == "[idle]":
            print(f"    {start} - {end}  {'.' * 20}  [idle]")
            continue

        if s.get("is_browser") and s.get("page_title"):
            detail = s["page_title"]
        else:
            detail = s.get("window_title", "")

        # Truncate
        if detail and len(detail) > 30:
            detail = detail[:27] + "..."

        proc_str = f"{proc:<18}"
        detail_str = f"{detail or '':<32}"
        print(f"    {start} – {end}  {proc_str} {detail_str} [{cat}]")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="ActivityLens — Daily Activity Report"
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Target date in YYYY-MM-DD format (default: today UTC)",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Force re-sessionize from raw snapshots (bypass cached sessions)",
    )
    args = parser.parse_args()

    config = Config()

    if not config.db_path.exists():
        print(f"  [ERROR] Database not found at {config.db_path}")
        print("  Run 'python src/main.py' first to start capturing.")
        sys.exit(1)

    conn = init_db(config.db_path)

    # Determine target date
    date_str = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    print("=" * 60)
    print(f"  ActivityLens — Daily Report  ({date_str})")
    print("=" * 60)

    # Run pipeline (sessionize + classify + store)
    sessions = run_pipeline(conn, config, date_str=date_str, force=args.raw)

    if not sessions:
        print(f"\n  No data found for {date_str}.")
        print("  Make sure the capture service has been running.")
        print("  (Or try: python tests/test_pipeline.py to seed test data)")
        conn.close()
        print("\n" + "=" * 60)
        return

    # Print report sections
    print_summary(sessions)
    print_top_activities(sessions)
    print_timeline(sessions)

    conn.close()
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
