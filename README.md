# 🔍 ActivityLens

**Your personal, privacy-first productivity dashboard.** ActivityLens runs locally on your Windows machine, silently tracking which apps and browser tabs you use throughout the day. It transforms raw window snapshots into meaningful activity sessions, classifies them by productivity, and visualizes everything in a beautiful dark-themed web dashboard.

> **All data stays on your machine.** No cloud. No accounts. No telemetry.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **Window Capture** | Polls the active window every 5 seconds via Win32 API |
| **Privacy Blocklist** | Sensitive apps/titles are never recorded (configurable) |
| **Session Merging** | Raw snapshots → intelligent activity sessions |
| **Productivity Classifier** | Auto-labels sessions as productive / neutral / distracting |
| **Daily Dashboard** | Donut charts, timeline bar, top apps, session detail modals |
| **Weekly Analytics** | 7-day trend charts, stacked bar breakdowns, streak tracking |
| **Browsing History** | Aggregated browser activity with search & category filters |
| **Continue Panel** | "Continue where you left off" — shows your recent browser tabs |
| **Handoff Prompt** | Generate a context prompt to continue your project in any AI chatbot |
| **Data Retention** | Auto-deletes raw snapshots older than 30 days |

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────┐
│  main.py (Capture Loop)                              │
│  ┌────────────┐   ┌──────────┐   ┌──────────────┐   │
│  │ Win32 API  │──▶│ Blocklist│──▶│ SQLite Store │   │
│  │ (capture)  │   │ (privacy)│   │  (storage)   │   │
│  └────────────┘   └──────────┘   └──────┬───────┘   │
└─────────────────────────────────────────┼────────────┘
                                          │
┌─────────────────────────────────────────▼────────────┐
│  Pipeline (on-demand)                                │
│  ┌────────────┐   ┌────────────┐   ┌────────────┐   │
│  │ Sessionizer│──▶│ Classifier │──▶│   Store    │   │
│  │  (merge)   │   │  (label)   │   │ (sessions) │   │
│  └────────────┘   └────────────┘   └────────────┘   │
└─────────────────────────────────────────┬────────────┘
                                          │
┌─────────────────────────────────────────▼────────────┐
│  Flask Server (server.py)                            │
│  ┌────────────────────────────────────────────────┐  │
│  │  REST API: /api/sessions, /api/summary,        │  │
│  │  /api/top-apps, /api/weekly, /api/streak,      │  │
│  │  /api/history, /api/recent-sites, /api/handoff │  │
│  └────────────────────┬───────────────────────────┘  │
└───────────────────────┼──────────────────────────────┘
                        │
┌───────────────────────▼──────────────────────────────┐
│  React Dashboard (Vite)                              │
│  Daily View │ Weekly View │ Browsing History │ Handoff│
└──────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.11+** with `pip`
- **Node.js 18+** with `npm`
- **Windows 10/11** (uses Win32 API for window capture)

### 1. Install Dependencies

```bash
# Python
pip install -r requirements.txt

# Dashboard
cd dashboard
npm install
cd ..
```

### 2. Seed Demo Data (optional)

```bash
python src/seed_data.py --days 7
```

This generates 7 days of realistic activity data so you can explore the dashboard immediately.

### 3. Build & Run

```bash
# Build the React dashboard
cd dashboard
npm run build
cd ..

# Start the server
python src/server.py
```

Open **http://127.0.0.1:5000** in your browser.

### 4. Start Capturing (optional)

To track your real activity:

```bash
python src/main.py
```

This runs in the foreground. Press `Ctrl+C` to stop.

---

## 📁 Project Structure

```
Activity-Lens/
├── config.yaml          # All configuration (polling, privacy, classification)
├── requirements.txt     # Python dependencies
├── src/
│   ├── main.py          # Capture polling loop
│   ├── capture.py       # Win32 window capture + browser detection
│   ├── config.py        # YAML config loader with defaults
│   ├── storage.py       # SQLite schema + all DB operations
│   ├── sessionizer.py   # Merge snapshots → activity sessions
│   ├── classifier.py    # Label sessions by productivity
│   ├── pipeline.py      # Orchestrate: sessionize → classify → store
│   ├── report.py        # CLI daily report
│   ├── server.py        # Flask API + dashboard serving
│   ├── handoff.py       # Project context prompt generator
│   ├── seed_data.py     # Demo data generator
│   └── inspect_db.py    # DB inspection utility
├── dashboard/
│   ├── src/
│   │   ├── App.jsx      # Main app with date nav + tab routing
│   │   ├── api.js       # API client + helpers
│   │   └── components/  # 15 React components
│   └── vite.config.js   # Vite + Flask proxy config
├── tests/               # pytest test suite
└── data/
    └── activity.db      # SQLite database (gitignored)
```

---

## ⚙️ Configuration

Edit `config.yaml` to customize:

- **Polling interval** — how often to capture (default: 5s)
- **Privacy blocklist** — apps/titles that are never recorded
- **Classification rules** — what's productive vs distracting
- **Retention** — how long to keep raw data (default: 30 days)
- **Dashboard** — host and port

---

## 🔒 Privacy Design

ActivityLens was built with privacy as a core constraint:

1. **Local-only** — no network requests, no cloud, no analytics
2. **Capture-time blocking** — sensitive apps are never written to disk
3. **Schema as boundary** — no content/keystroke columns exist in the DB
4. **Time-limited retention** — raw data auto-expires after 30 days
5. **Title-only tracking** — we capture window titles, never screen content

---

## 🧪 Testing

```bash
python -m pytest tests/ -v
```

Tests cover the capture module, classifier, sessionizer, and pipeline — all using synthetic data so they run without Win32 APIs.

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Capture | Python + pywin32 + psutil |
| Storage | SQLite (WAL mode) |
| Backend | Flask |
| Frontend | React 19 + Vite + Chart.js |
| Styling | Vanilla CSS (dark glassmorphism) |
| Config | YAML |

---

*Built with ❤️ — all data stays local.*
