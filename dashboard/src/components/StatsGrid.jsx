import { formatDuration } from '../api'

export default function StatsGrid({ summary, sessions, streak }) {
  const byCat = summary?.by_category || {}
  const idleSecs = byCat.idle?.seconds || 0
  const totalSecs = summary?.total_seconds || 0
  const activeSecs = totalSecs - idleSecs
  const prodSecs = byCat.productive?.seconds || 0
  const prodPct = activeSecs > 0 ? Math.round((prodSecs / activeSecs) * 100) : 0
  const activeSessions = sessions.filter(s => s.process_name !== '[idle]').length

  return (
    <div className="stats-grid">
      <div className="card stat-card">
        <div className="stat-value">{formatDuration(totalSecs)}</div>
        <div className="stat-label">Total Time</div>
      </div>
      <div className="card stat-card">
        <div className="stat-value" style={{ color: 'var(--productive)' }}>
          {formatDuration(prodSecs)}
        </div>
        <div className="stat-label">Productive</div>
        <div className="stat-sub">{prodPct}% of active time</div>
      </div>
      <div className="card stat-card">
        <div className="stat-value">{activeSessions}</div>
        <div className="stat-label">Sessions</div>
      </div>
      <div className="card stat-card">
        <div className="stat-value" style={{ color: 'var(--accent)' }}>{streak}</div>
        <div className="stat-label">Day Streak</div>
        <div className="stat-sub">&gt;50% productive</div>
      </div>
    </div>
  )
}
