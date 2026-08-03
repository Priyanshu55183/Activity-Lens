import { useState, useEffect, useMemo } from 'react'
import { fetchBrowsingHistory, formatDuration, formatTime } from '../api'

export default function BrowsingHistory({ dateStr, onEmpty, onLoading }) {
  const [sites, setSites] = useState([])
  const [loaded, setLoaded] = useState(false)
  const [search, setSearch] = useState('')
  const [filterCat, setFilterCat] = useState('all')
  const [expandedId, setExpandedId] = useState(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      onLoading(true)
      onEmpty(false)
      try {
        const res = await fetchBrowsingHistory(dateStr)
        if (!cancelled) {
          const s = res.sites || []
          setSites(s)
          setLoaded(true)
          if (s.length === 0) onEmpty(true)
        }
      } catch (err) {
        console.error('Failed to load browsing history:', err)
        if (!cancelled) onEmpty(true)
      }
      if (!cancelled) onLoading(false)
    }
    load()
    return () => { cancelled = true }
  }, [dateStr, onEmpty, onLoading])

  const filtered = useMemo(() => {
    let result = sites
    if (search) {
      const q = search.toLowerCase()
      result = result.filter(s =>
        s.page_title.toLowerCase().includes(q) ||
        s.process_name.toLowerCase().includes(q)
      )
    }
    if (filterCat !== 'all') {
      result = result.filter(s => s.category === filterCat)
    }
    return result
  }, [sites, search, filterCat])

  const totalTime = useMemo(
    () => sites.reduce((sum, s) => sum + (s.total_seconds || 0), 0),
    [sites]
  )
  const totalVisits = useMemo(
    () => sites.reduce((sum, s) => sum + (s.visit_count || 0), 0),
    [sites]
  )

  if (!loaded || sites.length === 0) return null

  const categories = ['all', 'productive', 'neutral', 'distracting']

  return (
    <div className="view-content">
      {/* Stats row */}
      <div className="bh-stats-row">
        <div className="card bh-stat">
          <div className="stat-value">{sites.length}</div>
          <div className="stat-label">Sites Visited</div>
        </div>
        <div className="card bh-stat">
          <div className="stat-value">{formatDuration(totalTime)}</div>
          <div className="stat-label">Total Browsing</div>
        </div>
        <div className="card bh-stat">
          <div className="stat-value">{totalVisits}</div>
          <div className="stat-label">Total Visits</div>
        </div>
      </div>

      {/* Search + filter */}
      <div className="bh-controls card">
        <div className="bh-search-wrapper">
          <span className="bh-search-icon">&#x1F50D;</span>
          <input
            className="bh-search"
            type="text"
            placeholder="Search sites..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            id="browsing-history-search"
          />
          {search && (
            <button className="bh-search-clear" onClick={() => setSearch('')}>&#x2715;</button>
          )}
        </div>
        <div className="bh-filters">
          {categories.map(cat => (
            <button
              key={cat}
              className={`bh-filter-chip ${filterCat === cat ? 'active' : ''} ${cat !== 'all' ? cat : ''}`}
              onClick={() => setFilterCat(cat)}
            >
              {cat === 'all' ? 'All' : cat.charAt(0).toUpperCase() + cat.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Site list */}
      <div className="card">
        <div className="card-title">
          Browsing History {filtered.length !== sites.length && `(${filtered.length} of ${sites.length})`}
        </div>

        {filtered.length === 0 ? (
          <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-muted)' }}>
            No sites match your search
          </div>
        ) : (
          <div className="bh-list">
            {filtered.map((site) => {
              const isExpanded = expandedId === site.id

              return (
                <div
                  className={`bh-item ${isExpanded ? 'expanded' : ''}`}
                  key={site.id}
                  onClick={() => setExpandedId(isExpanded ? null : site.id)}
                >
                  <div className="bh-item-main">
                    <div className="bh-item-icon">🌐</div>
                    <div className="bh-item-info">
                      <div className="bh-item-title">{site.page_title}</div>
                      <div className="bh-item-meta">
                        <span className="bh-item-browser">{site.process_name}</span>
                        <span className="bh-item-dot">·</span>
                        <span>{site.visit_count} visit{site.visit_count !== 1 ? 's' : ''}</span>
                      </div>
                    </div>
                    <div className="bh-item-right">
                      <span className="bh-item-duration">{formatDuration(site.total_seconds)}</span>
                      <span className={`category-badge ${site.category}`}>{site.category}</span>
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="bh-item-details">
                      <div className="bh-detail-grid">
                        <div className="bh-detail">
                          <span className="bh-detail-label">First Seen</span>
                          <span className="bh-detail-value">{formatTime(site.first_seen)}</span>
                        </div>
                        <div className="bh-detail">
                          <span className="bh-detail-label">Last Seen</span>
                          <span className="bh-detail-value">{formatTime(site.last_seen)}</span>
                        </div>
                        <div className="bh-detail">
                          <span className="bh-detail-label">Total Time</span>
                          <span className="bh-detail-value">{formatDuration(site.total_seconds)}</span>
                        </div>
                        <div className="bh-detail">
                          <span className="bh-detail-label">Category</span>
                          <span className={`category-badge ${site.category}`}>{site.category}</span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
