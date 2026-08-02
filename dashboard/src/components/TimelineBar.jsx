import { useState } from 'react'
import { formatDuration, formatTime } from '../api'

export default function TimelineBar({ sessions }) {
  const [tooltip, setTooltip] = useState(null)

  const active = sessions.filter(s => s.duration_seconds >= 5)
  if (active.length === 0) return null

  const totalDuration = active.reduce((sum, s) => sum + s.duration_seconds, 0)
  const firstTime = formatTime(active[0].start_time)
  const lastTime = formatTime(active[active.length - 1].end_time)

  return (
    <div className="card timeline-bar-container">
      <div className="card-title">Activity Timeline</div>
      <div className="timeline-bar">
        {active.map((session, i) => {
          const pct = (session.duration_seconds / totalDuration) * 100
          const appName = session.is_browser && session.page_title
            ? `${session.process_name} (${session.page_title})`
            : session.process_name

          return (
            <div
              key={i}
              className={`timeline-segment ${session.category || 'neutral'}`}
              style={{ width: `${Math.max(pct, 0.3)}%` }}
              onMouseEnter={() => setTooltip({ appName, session })}
              onMouseMove={(e) => setTooltip(prev => prev ? { ...prev, x: e.clientX, y: e.clientY } : null)}
              onMouseLeave={() => setTooltip(null)}
            />
          )
        })}
      </div>
      <div className="timeline-labels">
        <span>{firstTime}</span>
        <span>{lastTime}</span>
      </div>
      <div className="legend">
        <div className="legend-item"><div className="legend-dot" style={{ background: 'var(--productive)' }} />Productive</div>
        <div className="legend-item"><div className="legend-dot" style={{ background: 'var(--neutral)' }} />Neutral</div>
        <div className="legend-item"><div className="legend-dot" style={{ background: 'var(--distracting)' }} />Distracting</div>
        <div className="legend-item"><div className="legend-dot" style={{ background: 'var(--idle)' }} />Idle</div>
      </div>

      {tooltip && (
        <div
          className="timeline-tooltip"
          style={{ left: (tooltip.x || 0) + 12, top: (tooltip.y || 0) - 10 }}
        >
          <strong>{tooltip.appName}</strong><br />
          {formatTime(tooltip.session.start_time)} - {formatTime(tooltip.session.end_time)}<br />
          {formatDuration(tooltip.session.duration_seconds)} | {tooltip.session.category}
        </div>
      )}
    </div>
  )
}
