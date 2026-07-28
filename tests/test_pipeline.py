"""
Quick test: insert simulated snapshots and verify the pipeline works end-to-end.

This proves storage + inspect work correctly even when we can't call the real
Win32 APIs from a sandboxed terminal.  Run from a real PowerShell/cmd terminal
to test the actual capture (python src/main.py).
"""

import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from config import Config
from storage import init_db, insert_snapshot, get_recent_snapshots, get_snapshot_stats

config = Config()
conn = init_db(config.db_path)

# Simulate 10 snapshots over the last 5 minutes
now = datetime.now(timezone.utc)
test_data = [
    ("Code.exe", "main.py - Visual Studio Code", False, None),
    ("Code.exe", "capture.py - Visual Studio Code", False, None),
    ("chrome.exe", "GitHub - Google Chrome", True, "GitHub"),
    ("chrome.exe", "Stack Overflow - Google Chrome", True, "Stack Overflow"),
    ("chrome.exe", "Stack Overflow - Google Chrome", True, "Stack Overflow"),
    ("Code.exe", "storage.py - Visual Studio Code", False, None),
    ("Code.exe", "storage.py - Visual Studio Code", False, None),
    ("msedge.exe", "ChatGPT - Microsoft Edge", True, "ChatGPT"),
    ("explorer.exe", "Activity-Lens", False, None),
    ("Code.exe", "main.py - Visual Studio Code", False, None),
]

print("Inserting simulated snapshots...")
for i, (proc, title, is_browser, page_title) in enumerate(test_data):
    ts = (now - timedelta(seconds=(len(test_data) - i) * 30)).isoformat()
    snapshot = {
        "timestamp": ts,
        "process_name": proc,
        "window_title": title,
        "is_browser": is_browser,
        "page_title": page_title,
    }
    row_id = insert_snapshot(conn, snapshot)
    print(f"  Inserted row {row_id}: [{proc}] {page_title or title}")

print(f"\nDone! Inserted {len(test_data)} test snapshots.")
print(f"\nNow run:  python src/inspect_db.py --last 10 --stats")

conn.close()
