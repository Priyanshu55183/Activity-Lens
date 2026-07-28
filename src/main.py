"""
ActivityLens – Main Polling Loop
=================================

Entry point for the capture system.  Runs an infinite loop that:
    1. Captures the active window snapshot
    2. Stores it in SQLite (if not blocked)
    3. Sleeps for the configured interval
    4. Periodically enforces data retention

Run with:
    python src/main.py

Stop with Ctrl+C — it shuts down cleanly.

🎯 Interview-relevant: Polling loop design
    This is the simplest correct architecture: a single-threaded loop
    with a sleep.  At 5s intervals, there's no need for threading,
    asyncio, or a scheduler.  The sleep is the bottleneck by design —
    the capture + insert takes < 1ms.
    
    If we needed sub-second polling or multiple concurrent tasks, we'd
    move to asyncio or a scheduler like APScheduler.  But for our use
    case, simplicity wins.
"""

import sys
import time
import signal

# Add src/ to path so imports work when running from project root
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import Config
from capture import capture_snapshot
from storage import init_db, insert_snapshot, enforce_retention


# How often to run retention cleanup (every N captures, not every loop)
_RETENTION_CHECK_INTERVAL = 100


def format_snapshot_log(snapshot: dict) -> str:
    """Format a snapshot for console output — readable, one-line."""
    ts = snapshot["timestamp"][:19].replace("T", " ")  # trim microseconds
    proc = snapshot["process_name"]
    
    if snapshot["is_browser"] and snapshot["page_title"]:
        detail = f"[{proc}] {snapshot['page_title']}"
    else:
        title = snapshot["window_title"]
        # Truncate long titles for readability
        if len(title) > 60:
            title = title[:57] + "..."
        detail = f"[{proc}] {title}"
    
    return f"  {ts}  │  {detail}"


def main():
    """Main entry point — load config, init DB, start polling."""

    print("=" * 60)
    print("  ActivityLens — Capture Service")
    print("=" * 60)

    # --- Setup ---
    config = Config()
    print(f"\n  Config:  {config}")
    print(f"  DB path: {config.db_path}")
    print(f"  Poll:    every {config.polling_interval}s")
    print(f"  Blocked: {len(config.blocklist_processes)} processes, "
          f"{len(config.blocklist_title_patterns)} title patterns")
    print(f"\n  Press Ctrl+C to stop.\n")
    print("-" * 60)

    conn = init_db(config.db_path)
    
    capture_count = 0
    blocked_count = 0
    
    # --- Graceful shutdown ---
    running = True
    
    def handle_shutdown(signum, frame):
        nonlocal running
        running = False
    
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # --- Main loop ---
    try:
        while running:
            snapshot = capture_snapshot(config)

            if snapshot is not None:
                insert_snapshot(conn, snapshot)
                capture_count += 1
                print(format_snapshot_log(snapshot))
            else:
                blocked_count += 1

            # Periodic retention enforcement
            if capture_count > 0 and capture_count % _RETENTION_CHECK_INTERVAL == 0:
                deleted = enforce_retention(conn, config.retention_days)
                if deleted > 0:
                    print(f"  [cleanup] Retention: deleted {deleted} old snapshots")

            time.sleep(config.polling_interval)

    except Exception as e:
        print(f"\n  [ERROR] Error: {e}")
        raise
    
    finally:
        # Clean shutdown
        conn.close()
        print("\n" + "-" * 60)
        print(f"  Stopped. Captured {capture_count} snapshots, "
              f"blocked/skipped {blocked_count}.")
        print(f"  Data saved to: {config.db_path}")
        print("=" * 60)


if __name__ == "__main__":
    main()
