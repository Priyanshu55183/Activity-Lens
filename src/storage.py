"""
ActivityLens – SQLite Storage Layer
=====================================

Handles all database operations: creating the schema, inserting snapshots,
enforcing retention limits, and querying recent data.

Why SQLite over JSON Lines:
    - Indexed queries (by timestamp) for efficient sessionization on Day 2
    - Single file, fully local — no server process
    - Built-in concurrency handling (WAL mode)
    - Python's sqlite3 module is in the standard library — zero extra deps
    
    JSON Lines would be simpler for append-only writes, but querying
    "all snapshots between time X and Y" would require reading every line.
    At ~17K rows/day, that gets slow fast.

Schema design:
    The snapshots table stores exactly what capture.py produces — no more,
    no less.  We store facts (app name, window title, durations) but never
    content (no keystrokes, no message bodies, no screen text).
    
    🎯 Interview-relevant: Schema as privacy boundary
        The schema itself encodes what data we're willing to store.
        There's no "content" or "text" column — it's not just that we
        don't fill it, it doesn't exist.  This makes the privacy guarantee
        structural, not just behavioral.
"""

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT    NOT NULL,      -- ISO 8601 UTC
    process_name TEXT   NOT NULL,
    window_title TEXT,
    is_browser  INTEGER DEFAULT 0,    -- 0 = false, 1 = true
    page_title  TEXT,                  -- extracted page title (browsers only)
    created_at  TEXT    DEFAULT (datetime('now'))
);
"""

_CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp 
ON snapshots(timestamp);
"""

# --- Sessions table (Day 2) ---

_CREATE_SESSIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    start_time       TEXT    NOT NULL,
    end_time         TEXT    NOT NULL,
    duration_seconds REAL    NOT NULL,
    process_name     TEXT    NOT NULL,
    window_title     TEXT,
    is_browser       INTEGER DEFAULT 0,
    page_title       TEXT,
    snapshot_count   INTEGER DEFAULT 1,
    category         TEXT    DEFAULT 'neutral',
    created_at       TEXT    DEFAULT (datetime('now'))
);
"""

_CREATE_SESSIONS_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_sessions_start_time
ON sessions(start_time);
"""

# --- Browsing history table (aggregated browser visits) ---

_CREATE_BROWSING_HISTORY_SQL = """
CREATE TABLE IF NOT EXISTS browsing_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date            TEXT    NOT NULL,
    page_title      TEXT    NOT NULL,
    process_name    TEXT    NOT NULL,
    first_seen      TEXT    NOT NULL,
    last_seen       TEXT    NOT NULL,
    total_seconds   REAL    DEFAULT 0,
    visit_count     INTEGER DEFAULT 1,
    category        TEXT    DEFAULT 'neutral',
    created_at      TEXT    DEFAULT (datetime('now'))
);
"""

_CREATE_BROWSING_HISTORY_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_browsing_history_date
ON browsing_history(date);
"""


# ---------------------------------------------------------------------------
# Database Initialization
# ---------------------------------------------------------------------------

def init_db(db_path: str | Path) -> sqlite3.Connection:
    """
    Create the database file (and parent directories) if they don't exist,
    create the snapshots table and index, and return a connection.
    
    Uses WAL (Write-Ahead Logging) mode for better concurrent read/write
    performance — important if we later want to query the DB while capture
    is running (e.g. the inspect tool).
    
    🎯 Interview-relevant: WAL mode
        Default SQLite uses rollback journals, which lock the entire DB
        during writes.  WAL mode allows readers and a single writer to
        operate concurrently.  This matters when the inspect tool reads
        while main.py is writing every 5 seconds.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    
    conn.execute(_CREATE_TABLE_SQL)
    conn.execute(_CREATE_INDEX_SQL)
    conn.execute(_CREATE_SESSIONS_TABLE_SQL)
    conn.execute(_CREATE_SESSIONS_INDEX_SQL)
    conn.execute(_CREATE_BROWSING_HISTORY_SQL)
    conn.execute(_CREATE_BROWSING_HISTORY_INDEX_SQL)
    conn.commit()

    return conn


# ---------------------------------------------------------------------------
# Insert
# ---------------------------------------------------------------------------

def insert_snapshot(conn: sqlite3.Connection, snapshot: dict) -> int:
    """
    Insert a single snapshot row and return its ID.
    
    The snapshot dict comes directly from capture.capture_snapshot().
    We map is_browser (bool) → integer (0/1) for SQLite compatibility.
    """
    cursor = conn.execute(
        """
        INSERT INTO snapshots (timestamp, process_name, window_title, is_browser, page_title)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            snapshot["timestamp"],
            snapshot["process_name"],
            snapshot["window_title"],
            1 if snapshot["is_browser"] else 0,
            snapshot["page_title"],
        ),
    )
    conn.commit()
    return cursor.lastrowid


# ---------------------------------------------------------------------------
# Retention Enforcement
# ---------------------------------------------------------------------------

def enforce_retention(conn: sqlite3.Connection, retention_days: int) -> int:
    """
    Delete snapshots older than `retention_days` and return the count deleted.
    
    Called periodically (e.g. every 100 captures) rather than on every insert
    to avoid unnecessary I/O.  The cutoff is calculated in UTC to match
    our stored timestamps.
    
    🎯 Interview-relevant: Retention as privacy mechanism
        Raw capture data has a fixed TTL.  Even if someone gains access to
        the DB file, they can only see the last N days of raw snapshots.
        Compiled episodes (Day 3) can be kept longer since they're already
        aggregated and contain less detail.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    cutoff_iso = cutoff.isoformat()

    cursor = conn.execute(
        "DELETE FROM snapshots WHERE timestamp < ?",
        (cutoff_iso,),
    )
    conn.commit()
    return cursor.rowcount


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def get_recent_snapshots(
    conn: sqlite3.Connection,
    minutes: int = 60,
) -> list[dict]:
    """
    Fetch snapshots from the last `minutes` minutes.
    Returns a list of dicts (one per row), ordered by timestamp ascending.
    
    Used by the inspect tool and will be used by Day 2's sessionizer.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    cutoff_iso = cutoff.isoformat()

    cursor = conn.execute(
        """
        SELECT id, timestamp, process_name, window_title, is_browser, page_title
        FROM snapshots
        WHERE timestamp >= ?
        ORDER BY timestamp ASC
        """,
        (cutoff_iso,),
    )

    columns = ["id", "timestamp", "process_name", "window_title", "is_browser", "page_title"]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_snapshots_for_date(
    conn: sqlite3.Connection,
    date_str: str,
) -> list[dict]:
    """
    Fetch all snapshots for a given date (YYYY-MM-DD format).
    
    Used by the Day 2 pipeline to sessionize a full day's data.
    The date is matched against the first 10 characters of the ISO timestamp.
    """
    cursor = conn.execute(
        """
        SELECT id, timestamp, process_name, window_title, is_browser, page_title
        FROM snapshots
        WHERE substr(timestamp, 1, 10) = ?
        ORDER BY timestamp ASC
        """,
        (date_str,),
    )

    columns = ["id", "timestamp", "process_name", "window_title", "is_browser", "page_title"]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_snapshot_stats(conn: sqlite3.Connection) -> list[dict]:
    """
    Return aggregate stats: count of snapshots per process, ordered by count.
    Useful for a quick overview of what apps have been tracked.
    """
    cursor = conn.execute(
        """
        SELECT process_name, COUNT(*) as count,
               MIN(timestamp) as first_seen,
               MAX(timestamp) as last_seen
        FROM snapshots
        GROUP BY process_name
        ORDER BY count DESC
        """
    )

    columns = ["process_name", "count", "first_seen", "last_seen"]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


# ---------------------------------------------------------------------------
# Sessions — Insert & Query  (Day 2)
# ---------------------------------------------------------------------------

def insert_sessions(conn: sqlite3.Connection, sessions: list[dict]) -> int:
    """
    Bulk-insert a list of classified session dicts.
    
    Returns the number of rows inserted.
    
    Each session dict is expected to have keys matching the sessions table
    columns (produced by the pipeline: sessionizer + classifier).
    """
    if not sessions:
        return 0

    cursor = conn.executemany(
        """
        INSERT INTO sessions
            (start_time, end_time, duration_seconds, process_name,
             window_title, is_browser, page_title, snapshot_count, category)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                s["start_time"],
                s["end_time"],
                s["duration_seconds"],
                s["process_name"],
                s.get("window_title"),
                1 if s.get("is_browser") else 0,
                s.get("page_title"),
                s.get("snapshot_count", 1),
                s.get("category", "neutral"),
            )
            for s in sessions
        ],
    )
    conn.commit()
    return cursor.rowcount


def get_sessions_for_date(
    conn: sqlite3.Connection,
    date_str: str,
) -> list[dict]:
    """
    Fetch all sessions for a given date (YYYY-MM-DD format).
    Ordered by start_time ascending.
    """
    cursor = conn.execute(
        """
        SELECT id, start_time, end_time, duration_seconds, process_name,
               window_title, is_browser, page_title, snapshot_count, category
        FROM sessions
        WHERE substr(start_time, 1, 10) = ?
        ORDER BY start_time ASC
        """,
        (date_str,),
    )

    columns = [
        "id", "start_time", "end_time", "duration_seconds", "process_name",
        "window_title", "is_browser", "page_title", "snapshot_count", "category",
    ]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_daily_summary(
    conn: sqlite3.Connection,
    date_str: str,
) -> dict:
    """
    Return aggregate stats for a given date, grouped by category.
    
    Returns:
        {
            "total_seconds": float,
            "by_category": {
                "productive": {"seconds": float, "session_count": int},
                "neutral":    {"seconds": float, "session_count": int},
                "distracting": {"seconds": float, "session_count": int},
                "idle":       {"seconds": float, "session_count": int},
            }
        }
    """
    cursor = conn.execute(
        """
        SELECT category,
               COALESCE(SUM(duration_seconds), 0) as total_seconds,
               COUNT(*) as session_count
        FROM sessions
        WHERE substr(start_time, 1, 10) = ?
        GROUP BY category
        """,
        (date_str,),
    )

    by_category = {}
    total_seconds = 0.0

    for row in cursor.fetchall():
        cat, secs, count = row
        by_category[cat] = {"seconds": secs, "session_count": count}
        total_seconds += secs

    return {
        "total_seconds": total_seconds,
        "by_category": by_category,
    }


# ---------------------------------------------------------------------------
# Weekly Analytics (Day 4)
# ---------------------------------------------------------------------------

def get_weekly_summary(
    conn: sqlite3.Connection,
    end_date_str: str,
) -> list[dict]:
    """
    Return 7 days of daily summaries ending on end_date_str (inclusive).
    
    Each entry contains:
        {
            "date": "2026-07-30",
            "total_seconds": float,
            "by_category": { ... }
        }
    
    Days with no data will have total_seconds=0 and empty by_category.
    """
    from datetime import date as date_type

    end_date = date_type.fromisoformat(end_date_str)
    days = []

    for i in range(6, -1, -1):  # 6 days ago → today
        day = end_date - timedelta(days=i)
        day_str = day.isoformat()
        summary = get_daily_summary(conn, day_str)
        summary["date"] = day_str
        days.append(summary)

    return days


def get_date_range_sessions(
    conn: sqlite3.Connection,
    start_date_str: str,
    end_date_str: str,
) -> list[dict]:
    """
    Fetch all sessions between start_date and end_date (inclusive).
    Ordered by start_time ascending.
    """
    cursor = conn.execute(
        """
        SELECT id, start_time, end_time, duration_seconds, process_name,
               window_title, is_browser, page_title, snapshot_count, category
        FROM sessions
        WHERE substr(start_time, 1, 10) >= ? AND substr(start_time, 1, 10) <= ?
        ORDER BY start_time ASC
        """,
        (start_date_str, end_date_str),
    )

    columns = [
        "id", "start_time", "end_time", "duration_seconds", "process_name",
        "window_title", "is_browser", "page_title", "snapshot_count", "category",
    ]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


# ---------------------------------------------------------------------------
# Browsing History — Aggregated browser visits
# ---------------------------------------------------------------------------

def insert_browsing_history(
    conn: sqlite3.Connection,
    sessions: list[dict],
    date_str: str,
) -> int:
    """
    Aggregate browser sessions into browsing_history records for a date.
    
    For each unique (date, page_title) combination, we upsert:
    - Accumulate total_seconds
    - Track first_seen / last_seen
    - Count visits
    
    Returns the number of rows upserted.
    """
    # Clear existing history for this date (idempotent)
    conn.execute(
        "DELETE FROM browsing_history WHERE date = ?",
        (date_str,),
    )

    # Aggregate browser sessions by page_title
    aggregated = {}
    for s in sessions:
        if not s.get("is_browser") or not s.get("page_title"):
            continue

        title = s["page_title"]
        if title not in aggregated:
            aggregated[title] = {
                "page_title": title,
                "process_name": s["process_name"],
                "first_seen": s["start_time"],
                "last_seen": s["end_time"],
                "total_seconds": 0.0,
                "visit_count": 0,
                "category": s.get("category", "neutral"),
            }

        rec = aggregated[title]
        rec["total_seconds"] += s.get("duration_seconds", 0)
        rec["visit_count"] += 1
        # Track earliest first_seen and latest last_seen
        if s["start_time"] < rec["first_seen"]:
            rec["first_seen"] = s["start_time"]
        if s["end_time"] > rec["last_seen"]:
            rec["last_seen"] = s["end_time"]

    if not aggregated:
        return 0

    rows = list(aggregated.values())
    conn.executemany(
        """
        INSERT INTO browsing_history
            (date, page_title, process_name, first_seen, last_seen,
             total_seconds, visit_count, category)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                date_str,
                r["page_title"],
                r["process_name"],
                r["first_seen"],
                r["last_seen"],
                r["total_seconds"],
                r["visit_count"],
                r["category"],
            )
            for r in rows
        ],
    )
    conn.commit()
    return len(rows)


def get_browsing_history_for_date(
    conn: sqlite3.Connection,
    date_str: str,
) -> list[dict]:
    """
    Get all browsing history entries for a date, sorted by total time spent.
    """
    cursor = conn.execute(
        """
        SELECT id, date, page_title, process_name, first_seen, last_seen,
               total_seconds, visit_count, category
        FROM browsing_history
        WHERE date = ?
        ORDER BY total_seconds DESC
        """,
        (date_str,),
    )

    columns = [
        "id", "date", "page_title", "process_name", "first_seen", "last_seen",
        "total_seconds", "visit_count", "category",
    ]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_recent_sites(
    conn: sqlite3.Connection,
    days: int = 7,
) -> list[dict]:
    """
    Get the most recent browsing activity across the last N days.
    
    Returns sites ordered by last_seen (most recent first), limited to 20.
    Used for the "Continue Where You Left Off" feature.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

    cursor = conn.execute(
        """
        SELECT id, date, page_title, process_name, first_seen, last_seen,
               total_seconds, visit_count, category
        FROM browsing_history
        WHERE date >= ?
        ORDER BY last_seen DESC
        LIMIT 20
        """,
        (cutoff,),
    )

    columns = [
        "id", "date", "page_title", "process_name", "first_seen", "last_seen",
        "total_seconds", "visit_count", "category",
    ]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_session_by_id(
    conn: sqlite3.Connection,
    session_id: int,
) -> dict | None:
    """
    Fetch a single session by ID. Returns None if not found.
    """
    cursor = conn.execute(
        """
        SELECT id, start_time, end_time, duration_seconds, process_name,
               window_title, is_browser, page_title, snapshot_count, category
        FROM sessions
        WHERE id = ?
        """,
        (session_id,),
    )

    row = cursor.fetchone()
    if row is None:
        return None

    columns = [
        "id", "start_time", "end_time", "duration_seconds", "process_name",
        "window_title", "is_browser", "page_title", "snapshot_count", "category",
    ]
    return dict(zip(columns, row))
