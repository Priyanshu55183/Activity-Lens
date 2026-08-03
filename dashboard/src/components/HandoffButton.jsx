import { useState, useCallback, useRef, useEffect } from 'react'
import { fetchJSON } from '../api'

export default function HandoffButton() {
  const [isOpen, setIsOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [data, setData] = useState(null)
  const [copied, setCopied] = useState(false)
  const modalRef = useRef(null)

  const handleGenerate = useCallback(async () => {
    setIsOpen(true)
    setLoading(true)
    setError(null)
    setData(null)

    try {
      const result = await fetchJSON('/api/handoff')
      setData(result)
    } catch (err) {
      setError(err.message || 'Failed to generate handoff prompt')
    } finally {
      setLoading(false)
    }
  }, [])

  const handleCopy = useCallback(async () => {
    if (!data?.prompt) return
    try {
      await navigator.clipboard.writeText(data.prompt)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Fallback for older browsers
      const textarea = document.createElement('textarea')
      textarea.value = data.prompt
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }, [data])

  const handleDownload = useCallback(() => {
    if (!data?.prompt) return
    const blob = new Blob([data.prompt], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${data.project || 'project'}-handoff.md`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }, [data])

  const handleClose = useCallback(() => {
    setIsOpen(false)
    setCopied(false)
  }, [])

  // Close on backdrop click
  const handleBackdropClick = useCallback((e) => {
    if (modalRef.current && !modalRef.current.contains(e.target)) {
      handleClose()
    }
  }, [handleClose])

  // Close on Escape key
  useEffect(() => {
    if (!isOpen) return
    const handleKey = (e) => {
      if (e.key === 'Escape') handleClose()
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [isOpen, handleClose])

  return (
    <>
      <button
        className="handoff-btn"
        onClick={handleGenerate}
        title="Generate a context prompt to continue this project in another AI chatbot"
        id="handoff-trigger"
      >
        <span className="handoff-btn-icon">&#x1F4CB;</span>
        <span className="handoff-btn-text">Handoff</span>
      </button>

      {isOpen && (
        <div className="handoff-overlay" onClick={handleBackdropClick}>
          <div className="handoff-modal" ref={modalRef}>
            <div className="handoff-modal-header">
              <div className="handoff-modal-title">
                <span className="handoff-modal-icon">&#x1F4CB;</span>
                <div>
                  <h2>Project Handoff</h2>
                  <p className="handoff-subtitle">
                    Copy this prompt into any AI chatbot to continue your project
                  </p>
                </div>
              </div>
              <button className="handoff-close" onClick={handleClose} title="Close">
                &#x2715;
              </button>
            </div>

            <div className="handoff-modal-body">
              {loading && (
                <div className="handoff-loading">
                  <div className="handoff-spinner"></div>
                  <p>Scanning project &amp; generating prompt...</p>
                </div>
              )}

              {error && (
                <div className="handoff-error">
                  <span className="handoff-error-icon">&#x26A0;</span>
                  <p>{error}</p>
                  <button className="handoff-retry-btn" onClick={handleGenerate}>
                    Try Again
                  </button>
                </div>
              )}

              {data && !loading && (
                <>
                  <div className="handoff-stats">
                    <div className="handoff-stat">
                      <span className="handoff-stat-value">{data.stats?.key_files || 0}</span>
                      <span className="handoff-stat-label">Files</span>
                    </div>
                    <div className="handoff-stat">
                      <span className="handoff-stat-value">{data.stats?.lines || 0}</span>
                      <span className="handoff-stat-label">Lines</span>
                    </div>
                    <div className="handoff-stat">
                      <span className="handoff-stat-value">
                        {data.stats?.characters ? `${(data.stats.characters / 1000).toFixed(1)}k` : '0'}
                      </span>
                      <span className="handoff-stat-label">Chars</span>
                    </div>
                  </div>

                  <div className="handoff-preview">
                    <pre className="handoff-code">{data.prompt}</pre>
                  </div>
                </>
              )}
            </div>

            {data && !loading && (
              <div className="handoff-modal-footer">
                <button className="handoff-action-btn secondary" onClick={handleDownload}>
                  <span>&#x2B07;</span> Download .md
                </button>
                <button
                  className={`handoff-action-btn primary ${copied ? 'copied' : ''}`}
                  onClick={handleCopy}
                >
                  <span>{copied ? '✓' : '&#x1F4CB;'}</span>
                  {copied ? 'Copied!' : 'Copy to Clipboard'}
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  )
}
