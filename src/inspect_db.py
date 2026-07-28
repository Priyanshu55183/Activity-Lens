"""
ActivityLens – Database Inspection Utility
===========================================

A small CLI tool to query and display captured data.  This is how you
answer the Day 1 goal: "see what raw captured data actually looks like."

Usage:
    python src/inspect_db.py                  # last 60 minutes
    python src/inspect_db.py --last 30        # last 30 minutes
    python src/inspect_db.py --stats          # count per process
    python src/inspect_db.py --last 120 --stats  # both
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import Config
from storage import init_db, get_recent_snapshots, get_snapshot_stats


def print_snapshots(snapshots: list[dict]):
    """Print snapshots as a formatted table."""
    if not snapshots:
        print("  No snapshots found in this time range.")
        return

    print(f"\n  {'ID':>6}  {'Timestamp':19}  {'Process':<25}  {'Title / Page'}")
    print("  " + "-" * 90)

    for s in snapshots:
        ts = s["timestamp"][:19].replace("T", " ")
        proc = s["process_name"][:25]
        
        if s["is_browser"] and s["page_title"]:
            title = f"[web] {s['page_title']}"
        else:
            title = s["window_title"] or ""
        
        # Truncate long titles
        if len(title) > 50:
            title = title[:47] + "..."

        print(f"  {s['id']:>6}  {ts}  {proc:<25}  {title}")

    print(f"\n  Total: {len(snapshots)} snapshots")


def print_stats(stats: list[dict]):
    """Print per-process statistics."""
    if not stats:
        print("  No data in database.")
        return

    print(f"\n  {'Process':<30}  {'Count':>7}  {'First Seen':19}  {'Last Seen':19}")
    print("  " + "-" * 82)

    for s in stats:
        first = s["first_seen"][:19].replace("T", " ")
        last = s["last_seen"][:19].replace("T", " ")
        print(f"  {s['process_name']:<30}  {s['count']:>7}  {first}  {last}")


def main():
    parser = argparse.ArgumentParser(
        description="Inspect ActivityLens captured data"
    )
    parser.add_argument(
        "--last",
        type=int,
        default=60,
        help="Show snapshots from the last N minutes (default: 60)",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show per-process statistics",
    )
    args = parser.parse_args()

    config = Config()
    
    if not config.db_path.exists():
        print(f"  [ERROR] Database not found at {config.db_path}")
        print("  Run 'python src/main.py' first to start capturing.")
        sys.exit(1)

    conn = init_db(config.db_path)

    print("=" * 60)
    print("  ActivityLens — Data Inspector")
    print("=" * 60)

    if args.stats:
        print(f"\n  [Stats] Statistics (all time):")
        stats = get_snapshot_stats(conn)
        print_stats(stats)

    print(f"\n  [Recent] Snapshots (last {args.last} minutes):")
    snapshots = get_recent_snapshots(conn, minutes=args.last)
    print_snapshots(snapshots)

    conn.close()
    print()


if __name__ == "__main__":
    main()
