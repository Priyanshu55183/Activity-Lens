import { formatDuration, formatTime } from '../api'

export default function SessionList({ sessions, onSessionClick }) {
  const active = sessions.filter(s => s.process_name !== '[idle]' && s.duration_seconds >= 10)

  if (active.length === 0) {
    return (
      <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-muted)' }}>
        No significant sessions
      </div>
    )
  }

  return (
    <div className="session-list">
      {active.map((s, i) => {
        const detail = s.is_browser && s.page_title
          ? s.page_title
          : (s.window_title || '')
        const truncDetail = detail.length > 40 ? detail.slice(0, 37) + '...' : detail

        return (
          <div
            className="session-item clickable"
            key={i}
            onClick={() => onSessionClick && onSessionClick(s)}
            title="Click for details"
          >
            <span className="session-time">
              {formatTime(s.start_time)} - {formatTime(s.end_time)}
            </span>
            <div className="session-app">
              <span className="session-app-name">{s.process_name}</span>
              <span className="session-app-detail">{truncDetail}</span>
            </div>
            <span className="session-duration">{formatDuration(s.duration_seconds)}</span>
            <span className={`category-badge ${s.category}`}>{s.category}</span>
          </div>
        )
      })}
    </div>
  )
}
