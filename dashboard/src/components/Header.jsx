import { useRef } from 'react'
import { dateStr } from '../api'
import HandoffButton from './HandoffButton'

export default function Header({ currentDate, currentTab, isToday, onPrevDay, onNextDay, onDatePick, onTabChange }) {
  const dateInputRef = useRef(null)

  const displayDate = currentDate.toLocaleDateString('en-US', {
    weekday: 'short', year: 'numeric', month: 'short', day: 'numeric'
  })

  return (
    <header className="header">
      <div className="header-inner">
        <div className="logo">
          <div className="logo-icon">&#x1F50D;</div>
          <h1>ActivityLens <span>Dashboard</span></h1>
        </div>

        <div className="date-nav">
          <button onClick={onPrevDay} title="Previous day">&#x25C0;</button>
          <div
            className="date-display"
            title="Click to pick date"
            onClick={() => dateInputRef.current?.showPicker?.()}
          >
            {displayDate}
            <input
              ref={dateInputRef}
              type="date"
              className="date-input"
              value={dateStr(currentDate)}
              onChange={e => onDatePick(e.target.value)}
            />
          </div>
          <button onClick={onNextDay} disabled={isToday} title="Next day">&#x25B6;</button>
        </div>

        <div className="tab-nav">
          <button
            className={`tab-btn ${currentTab === 'daily' ? 'active' : ''}`}
            onClick={() => onTabChange('daily')}
          >
            Daily
          </button>
          <button
            className={`tab-btn ${currentTab === 'weekly' ? 'active' : ''}`}
            onClick={() => onTabChange('weekly')}
          >
            Weekly
          </button>
          <button
            className={`tab-btn ${currentTab === 'history' ? 'active' : ''}`}
            onClick={() => onTabChange('history')}
          >
            History
          </button>
        </div>

        <HandoffButton />
      </div>
    </header>
  )
}
