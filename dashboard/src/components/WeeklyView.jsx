import { useState, useEffect } from 'react'
import { fetchJSON, formatDuration, dayName, categoryColor } from '../api'
import TrendChart from './TrendChart'
import DailyBarsChart from './DailyBarsChart'

export default function WeeklyView({ dateStr, onEmpty, onLoading }) {
  const [days, setDays] = useState([])
  const [streak, setStreak] = useState(0)
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    let cancelled = false
    async function load() {
      onLoading(true)
      onEmpty(false)
      try {
        const [weeklyRes, streakRes] = await Promise.all([
          fetchJSON(`/api/weekly/${dateStr}`),
          fetchJSON(`/api/streak/${dateStr}`),
        ])
        if (cancelled) return
        const d = weeklyRes.days || []
        setDays(d)
        setStreak(streakRes.streak || 0)
        setLoaded(true)
        if (d.every(x => x.total_seconds === 0)) onEmpty(true)
      } catch (err) {
        console.error('Failed to load weekly data:', err)
        if (!cancelled) onEmpty(true)
      }
      if (!cancelled) onLoading(false)
    }
    load()
    return () => { cancelled = true }
  }, [dateStr, onEmpty, onLoading])

  if (!loaded || days.every(d => d.total_seconds === 0)) return null

  const activeDays = days.filter(d => d.total_seconds > 0)
  const totalSecs = days.reduce((sum, d) => sum + d.total_seconds, 0)

  // Avg productive %
  const prodPcts = activeDays.map(d => {
    const byCat = d.by_category || {}
    const idleSecs = byCat.idle?.seconds || 0
    const activeSecs = d.total_seconds - idleSecs
    const prodSecs = byCat.productive?.seconds || 0
    return activeSecs > 0 ? (prodSecs / activeSecs) * 100 : 0
  })
  const avgProd = prodPcts.length > 0
    ? Math.round(prodPcts.reduce((a, b) => a + b, 0) / prodPcts.length)
    : 0

  // Best day
  let bestDay = '--'
  let bestProd = 0
  activeDays.forEach(d => {
    const prodSecs = d.by_category?.productive?.seconds || 0
    if (prodSecs > bestProd) { bestProd = prodSecs; bestDay = dayName(d.date) }
  })

  // Trend (first half vs second half)
  const firstHalf = prodPcts.slice(0, Math.ceil(prodPcts.length / 2))
  const secondHalf = prodPcts.slice(Math.ceil(prodPcts.length / 2))
  const firstAvg = firstHalf.length ? firstHalf.reduce((a, b) => a + b, 0) / firstHalf.length : 0
  const secondAvg = secondHalf.length ? secondHalf.reduce((a, b) => a + b, 0) / secondHalf.length : 0
  const trend = secondAvg - firstAvg

  let trendClass = 'flat', trendText = 'Steady'
  if (Math.abs(trend) >= 3) {
    if (trend > 0) { trendClass = 'up'; trendText = `▲ +${Math.round(trend)}%` }
    else { trendClass = 'down'; trendText = `▼ ${Math.round(trend)}%` }
  }

  return (
    <div className="view-content">
      {/* Header with streak */}
      <div className="weekly-header">
        <h2>Week Overview</h2>
        {streak > 0 && (
          <div className="streak-badge">
            <span className="streak-fire">&#x1F525;</span>
            <span>{streak}-day streak!</span>
          </div>
        )}
      </div>

      {/* Weekly stats */}
      <div className="weekly-stats-grid">
        <div className="card weekly-stat-card">
          <div className="stat-value">{formatDuration(totalSecs)}</div>
          <div className="stat-label">Week Total</div>
        </div>
        <div className="card weekly-stat-card">
          <div className="stat-value" style={{ color: 'var(--productive)' }}>{avgProd}%</div>
          <div className="stat-label">Avg Productive %</div>
          <div className={`trend-indicator ${trendClass}`}>{trendText}</div>
        </div>
        <div className="card weekly-stat-card">
          <div className="stat-value" style={{ color: 'var(--accent)' }}>{bestDay}</div>
          <div className="stat-label">Best Day</div>
        </div>
        <div className="card weekly-stat-card">
          <div className="stat-value">{activeDays.length}</div>
          <div className="stat-label">Days Tracked</div>
        </div>
      </div>

      {/* Charts */}
      <div className="weekly-grid">
        <div className="card">
          <div className="card-title">Productivity Trend (7 Days)</div>
          <div className="weekly-chart-container">
            <TrendChart days={days} />
          </div>
        </div>
        <div className="card">
          <div className="card-title">Daily Breakdown</div>
          <div className="weekly-chart-container">
            <DailyBarsChart days={days} />
          </div>
        </div>
      </div>

      {/* Day-by-day table */}
      <div className="card">
        <div className="card-title">Day-by-Day Summary</div>
        {days.map((d, i) => {
          const byCat = d.by_category || {}
          const idleSecs = byCat.idle?.seconds || 0
          const activeSecs = d.total_seconds - idleSecs
          const prodSecs = byCat.productive?.seconds || 0
          const prodPct = activeSecs > 0 ? Math.round((prodSecs / activeSecs) * 100) : 0

          if (d.total_seconds === 0) {
            return (
              <div className="weekly-table-row" key={i} style={{ opacity: 0.4 }}>
                <span className="session-time">{d.date}</span>
                <div className="session-app">
                  <span className="session-app-name">{dayName(d.date)}</span>
                  <span className="session-app-detail">No data</span>
                </div>
                <span className="session-duration">--</span>
                <span className="category-badge idle">--</span>
              </div>
            )
          }

          const barWidth = Math.min(prodPct, 100)
          const badgeCat = prodPct >= 50 ? 'productive' : prodPct >= 30 ? 'neutral' : 'distracting'

          return (
            <div className="weekly-table-row" key={i}>
              <span className="session-time">{d.date}</span>
              <div className="session-app">
                <span className="session-app-name">{dayName(d.date)}</span>
                <span className="session-app-detail">
                  <span className="prod-bar" style={{ width: `${barWidth}%`, maxWidth: 120 }} />
                  {prodPct}% productive
                </span>
              </div>
              <span className="session-duration">{formatDuration(d.total_seconds)}</span>
              <span className={`category-badge ${badgeCat}`}>{prodPct}%</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
