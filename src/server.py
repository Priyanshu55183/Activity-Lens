"""
ActivityLens - Dashboard API Server
======================================

Lightweight Flask server powering the web dashboard.

Endpoints:
    GET /                        -> Serves the React dashboard
    GET /api/sessions/<date>     -> Sessions for a date (YYYY-MM-DD)
    GET /api/summary/<date>      -> Category breakdown for a date
    GET /api/top-apps/<date>     -> Top apps ranked by duration
    GET /api/weekly/<end_date>   -> 7-day summary with daily breakdowns
    GET /api/streak/<date>       -> Current productive streak count

Usage:
    python src/server.py
"""

import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta, date as date_type

sys.path.insert(0, str(Path(__file__).resolve().parent))

from flask import Flask, jsonify, send_from_directory
from config import Config
from storage import (
    init_db,
    get_sessions_for_date,
    get_daily_summary,
    get_weekly_summary,
    get_browsing_history_for_date,
    get_recent_sites,
    get_session_by_id,
)
from pipeline import run_pipeline
from handoff import scan_file_tree, detect_key_files, get_git_context, generate_prompt


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

config = Config()

app = Flask(__name__, static_folder=None)

DASHBOARD_DIR = Path(__file__).resolve().parent.parent / "dashboard" / "dist"


def get_conn():
    """
    Create a fresh DB connection per-request.
    
    SQLite connections can't be shared across threads. Flask in debug mode
    uses a reloader that spawns threads, so we create a new connection for
    each request instead of reusing a global one.
    """
    return init_db(config.db_path)


# ---------------------------------------------------------------------------
# Dashboard serving (React build output)
# ---------------------------------------------------------------------------

@app.route("/")
def serve_dashboard():
    """Serve the React dashboard index.html."""
    return send_from_directory(str(DASHBOARD_DIR), "index.html")


@app.route("/<path:filename>")
def serve_static(filename):
    """Serve static assets from the React build directory."""
    file_path = DASHBOARD_DIR / filename
    if file_path.exists():
        return send_from_directory(str(DASHBOARD_DIR), filename)
    # SPA fallback: serve index.html for client-side routes
    return send_from_directory(str(DASHBOARD_DIR), "index.html")


# ---------------------------------------------------------------------------
# API: Daily endpoints
# ---------------------------------------------------------------------------

@app.route("/api/sessions/<date_str>")
def api_sessions(date_str):
    """Return sessions for a given date, running pipeline if needed."""
    try:
        date_type.fromisoformat(date_str)
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

    conn = get_conn()
    try:
        sessions = run_pipeline(conn, config, date_str=date_str)
        return jsonify({"date": date_str, "sessions": sessions})
    finally:
        conn.close()


@app.route("/api/summary/<date_str>")
def api_summary(date_str):
    """Return category breakdown for a date."""
    try:
        date_type.fromisoformat(date_str)
    except ValueError:
        return jsonify({"error": "Invalid date format."}), 400

    conn = get_conn()
    try:
        run_pipeline(conn, config, date_str=date_str)
        summary = get_daily_summary(conn, date_str)
        summary["date"] = date_str
        return jsonify(summary)
    finally:
        conn.close()


@app.route("/api/top-apps/<date_str>")
def api_top_apps(date_str):
    """Return top apps ranked by duration for a date."""
    try:
        date_type.fromisoformat(date_str)
    except ValueError:
        return jsonify({"error": "Invalid date format."}), 400

    conn = get_conn()
    try:
        sessions = run_pipeline(conn, config, date_str=date_str)

        app_totals = {}
        for s in sessions:
            if s["process_name"] == "[idle]":
                continue

            if s.get("is_browser") and s.get("page_title"):
                key = f"{s['process_name']} ({s['page_title']})"
            else:
                key = s["process_name"]

            cat = s.get("category", "neutral")
            if key not in app_totals:
                app_totals[key] = {"name": key, "seconds": 0, "category": cat}
            app_totals[key]["seconds"] += s["duration_seconds"]

        ranked = sorted(app_totals.values(), key=lambda x: x["seconds"], reverse=True)
        return jsonify({"date": date_str, "apps": ranked[:15]})
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# API: Weekly endpoints (Day 4)
# ---------------------------------------------------------------------------

@app.route("/api/weekly/<end_date_str>")
def api_weekly(end_date_str):
    """Return 7-day summary with daily breakdowns."""
    try:
        end_date = date_type.fromisoformat(end_date_str)
    except ValueError:
        return jsonify({"error": "Invalid date format."}), 400

    conn = get_conn()
    try:
        for i in range(6, -1, -1):
            day = end_date - timedelta(days=i)
            day_str = day.isoformat()
            run_pipeline(conn, config, date_str=day_str)

        weekly = get_weekly_summary(conn, end_date_str)
        return jsonify({"end_date": end_date_str, "days": weekly})
    finally:
        conn.close()


@app.route("/api/streak/<date_str>")
def api_streak(date_str):
    """
    Return the current productive streak count.
    A 'streak' is consecutive days where productive time > 50% of active time.
    Weekends are skipped.
    """
    try:
        check_date = date_type.fromisoformat(date_str)
    except ValueError:
        return jsonify({"error": "Invalid date format."}), 400

    conn = get_conn()
    try:
        streak = 0
        current = check_date

        for _ in range(90):
            if current.weekday() >= 5:
                current -= timedelta(days=1)
                continue

            summary = get_daily_summary(conn, current.isoformat())
            total = summary["total_seconds"]
            by_cat = summary["by_category"]

            if total == 0:
                break

            idle_secs = by_cat.get("idle", {}).get("seconds", 0)
            active_secs = total - idle_secs
            prod_secs = by_cat.get("productive", {}).get("seconds", 0)

            if active_secs > 0 and (prod_secs / active_secs) > 0.5:
                streak += 1
            else:
                break

            current -= timedelta(days=1)

        return jsonify({
            "date": date_str,
            "streak": streak,
            "threshold": "50% productive",
        })
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# API: Browsing History & Session Detail
# ---------------------------------------------------------------------------

@app.route("/api/history/<date_str>")
def api_history(date_str):
    """Return browsing history for a given date."""
    try:
        date_type.fromisoformat(date_str)
    except ValueError:
        return jsonify({"error": "Invalid date format."}), 400

    conn = get_conn()
    try:
        # Ensure pipeline has run for this date
        run_pipeline(conn, config, date_str=date_str)
        history = get_browsing_history_for_date(conn, date_str)
        return jsonify({"date": date_str, "sites": history})
    finally:
        conn.close()


@app.route("/api/recent-sites")
def api_recent_sites():
    """Return recent browsing activity for 'Continue Where You Left Off'."""
    conn = get_conn()
    try:
        sites = get_recent_sites(conn, days=7)
        return jsonify({"sites": sites})
    finally:
        conn.close()


@app.route("/api/session/<int:session_id>")
def api_session_detail(session_id):
    """Return detailed info for a single session."""
    conn = get_conn()
    try:
        session = get_session_by_id(conn, session_id)
        if session is None:
            return jsonify({"error": "Session not found."}), 404
        return jsonify({"session": session})
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# API: Handoff prompt generator
# ---------------------------------------------------------------------------

@app.route("/api/handoff")
def api_handoff():
    """
    Generate a handoff prompt for a project directory.

    Query params:
        path  – absolute path to scan (defaults to Activity-Lens project root)
    """
    from flask import request

    project_path = request.args.get("path")
    if project_path:
        project_path = Path(project_path).resolve()
    else:
        project_path = Path(__file__).resolve().parent.parent

    if not project_path.exists() or not project_path.is_dir():
        return jsonify({"error": f"Not a valid directory: {project_path}"}), 400

    hcfg = config.handoff_config
    ignore_dirs = hcfg["ignore_dirs"]
    ignore_exts = hcfg["ignore_extensions"]
    max_lines = hcfg["max_file_lines"]
    max_files = hcfg["max_files"]

    tree = scan_file_tree(project_path, ignore_dirs, ignore_exts)
    key_files = detect_key_files(project_path, ignore_dirs, ignore_exts, max_files)
    git_ctx = get_git_context(project_path)
    prompt = generate_prompt(project_path, tree, key_files, git_ctx, max_lines)

    return jsonify({
        "project": project_path.name,
        "prompt": prompt,
        "stats": {
            "lines": prompt.count("\n") + 1,
            "characters": len(prompt),
            "key_files": len(key_files),
        },
    })


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("  ActivityLens - Dashboard Server")
    print("=" * 60)
    print(f"\n  Open http://{config.dashboard_host}:{config.dashboard_port}")
    print(f"  Press Ctrl+C to stop.\n")

    app.run(
        host=config.dashboard_host,
        port=config.dashboard_port,
        debug=True,
    )
