import { useState, useEffect } from 'react'
import { fetchJSON, formatDuration } from '../api'
import StatsGrid from './StatsGrid'
import TimelineBar from './TimelineBar'
import DonutChart from './DonutChart'
import TopAppsChart from './TopAppsChart'
import SessionList from './SessionList'

export default function DailyView({ dateStr, onEmpty, onLoading }) {
  const [sessions, setSessions] = useState([])
  const [summary, setSummary] = useState(null)
  const [apps, setApps] = useState([])
  const [streak, setStreak] = useState(0)
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    let cancelled = false
    async function load() {
      onLoading(true)
      onEmpty(false)
      try {
        const [sessRes, sumRes, appRes, strRes] = await Promise.all([
          fetchJSON(`/api/sessions/${dateStr}`),
          fetchJSON(`/api/summary/${dateStr}`),
          fetchJSON(`/api/top-apps/${dateStr}`),
          fetchJSON(`/api/streak/${dateStr}`),
        ])
        if (cancelled) return
        const sess = sessRes.sessions || []
        setSessions(sess)
        setSummary(sumRes)
        setApps(appRes.apps || [])
        setStreak(strRes.streak || 0)
        setLoaded(true)
        if (sess.length === 0) onEmpty(true)
      } catch (err) {
        console.error('Failed to load daily data:', err)
        if (!cancelled) onEmpty(true)
      }
      if (!cancelled) onLoading(false)
    }
    load()
    return () => { cancelled = true }
  }, [dateStr, onEmpty, onLoading])

  if (!loaded || sessions.length === 0) return null

  return (
    <div className="view-content">
      <StatsGrid summary={summary} sessions={sessions} streak={streak} />
      <TimelineBar sessions={sessions} />
      <div className="charts-grid">
        <div className="card">
          <div className="card-title">Productivity Breakdown</div>
          <DonutChart summary={summary} />
        </div>
        <div className="card">
          <div className="card-title">Top Activities</div>
          <TopAppsChart apps={apps} />
        </div>
      </div>
      <div className="card">
        <div className="card-title">Session Details</div>
        <SessionList sessions={sessions} />
      </div>
    </div>
  )
}
