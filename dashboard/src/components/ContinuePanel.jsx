import { useState, useEffect } from 'react'
import { fetchRecentSites, formatDuration, formatTime } from '../api'

export default function ContinuePanel() {
  const [sites, setSites] = useState([])
  const [loaded, setLoaded] = useState(false)
  const [expanded, setExpanded] = useState(true)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const res = await fetchRecentSites()
        if (!cancelled) {
          setSites(res.sites || [])
          setLoaded(true)
        }
      } catch (err) {
        console.error('Failed to load recent sites:', err)
        if (!cancelled) setLoaded(true)
      }
    }
    load()
    return () => { cancelled = true }
  }, [])

  if (!loaded || sites.length === 0) return null

  // Deduplicate by page_title and take top 6
  const seen = new Set()
  const unique = []
  for (const site of sites) {
    if (!seen.has(site.page_title)) {
      seen.add(site.page_title)
      unique.push(site)
    }
    if (unique.length >= 6) break
  }

  return (
    <div className="continue-panel card">
      <div
        className="continue-header"
        onClick={() => setExpanded(e => !e)}
        role="button"
        tabIndex={0}
      >
        <div className="continue-title-row">
          <span className="continue-icon">&#x1F504;</span>
          <h3 className="card-title" style={{ margin: 0 }}>Continue Where You Left Off</h3>
        </div>
        <span className={`continue-chevron ${expanded ? 'open' : ''}`}>&#x25BC;</span>
      </div>

      {expanded && (
        <div className="continue-grid">
          {unique.map((site, i) => (
            <div className="continue-card" key={i}>
              <div className="continue-card-header">
                <span className="continue-card-icon">🌐</span>
                <span className={`category-badge ${site.category || 'neutral'}`}>
                  {site.category || 'neutral'}
                </span>
              </div>
              <div className="continue-card-title" title={site.page_title}>
                {site.page_title}
              </div>
              <div className="continue-card-meta">
                <span>{formatDuration(site.total_seconds)}</span>
                <span className="continue-card-dot">·</span>
                <span>{site.visit_count} visit{site.visit_count !== 1 ? 's' : ''}</span>
                <span className="continue-card-dot">·</span>
                <span>{site.date}</span>
              </div>
              <div className="continue-card-time">
                Last seen {formatTime(site.last_seen)}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
