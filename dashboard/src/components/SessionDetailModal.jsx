import { useEffect, useRef, useCallback } from 'react'
import { formatDuration, formatTime } from '../api'

export default function SessionDetailModal({ session, onClose }) {
  const modalRef = useRef(null)

  const handleBackdrop = useCallback((e) => {
    if (modalRef.current && !modalRef.current.contains(e.target)) {
      onClose()
    }
  }, [onClose])

  useEffect(() => {
    const handleKey = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [onClose])

  if (!session) return null

  const isBrowser = session.is_browser && session.page_title
  const categoryLabel = session.category || 'neutral'

  return (
    <div className="sdm-overlay" onClick={handleBackdrop}>
      <div className="sdm-modal" ref={modalRef}>
        {/* Header */}
        <div className="sdm-header">
          <div className="sdm-header-left">
            <div className={`sdm-icon ${categoryLabel}`}>
              {isBrowser ? '🌐' : '💻'}
            </div>
            <div>
              <h2 className="sdm-title">{session.process_name}</h2>
              <span className={`category-badge ${categoryLabel}`}>{categoryLabel}</span>
            </div>
          </div>
          <button className="sdm-close" onClick={onClose} title="Close">&#x2715;</button>
        </div>

        {/* Body */}
        <div className="sdm-body">
          {/* Page / Window title */}
          {isBrowser && (
            <div className="sdm-section">
              <div className="sdm-label">Page Title</div>
              <div className="sdm-value sdm-page-title">{session.page_title}</div>
            </div>
          )}

          {session.window_title && (
            <div className="sdm-section">
              <div className="sdm-label">Window Title</div>
              <div className="sdm-value">{session.window_title}</div>
            </div>
          )}

          {/* Time info grid */}
          <div className="sdm-grid">
            <div className="sdm-grid-item">
              <div className="sdm-grid-label">Start Time</div>
              <div className="sdm-grid-value">{formatTime(session.start_time)}</div>
            </div>
            <div className="sdm-grid-item">
              <div className="sdm-grid-label">End Time</div>
              <div className="sdm-grid-value">{formatTime(session.end_time)}</div>
            </div>
            <div className="sdm-grid-item">
              <div className="sdm-grid-label">Duration</div>
              <div className="sdm-grid-value sdm-highlight">
                {formatDuration(session.duration_seconds)}
              </div>
            </div>
            <div className="sdm-grid-item">
              <div className="sdm-grid-label">Snapshots</div>
              <div className="sdm-grid-value">{session.snapshot_count || '—'}</div>
            </div>
          </div>

          {/* Date */}
          {session.start_time && (
            <div className="sdm-section">
              <div className="sdm-label">Date</div>
              <div className="sdm-value">{session.start_time.slice(0, 10)}</div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
