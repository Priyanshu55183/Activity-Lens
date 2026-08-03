import { useState, useCallback } from 'react'
import './App.css'
import Header from './components/Header'
import DailyView from './components/DailyView'
import WeeklyView from './components/WeeklyView'
import BrowsingHistory from './components/BrowsingHistory'
import EmptyState from './components/EmptyState'
import { dateStr } from './api'

function App() {
  const [currentDate, setCurrentDate] = useState(() => {
    const now = new Date()
    return new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()))
  })
  const [currentTab, setCurrentTab] = useState('daily')
  const [isEmpty, setIsEmpty] = useState(false)
  const [loading, setLoading] = useState(false)

  const handlePrevDay = useCallback(() => {
    setCurrentDate(d => {
      const nd = new Date(d)
      nd.setUTCDate(nd.getUTCDate() - 1)
      return nd
    })
  }, [])

  const handleNextDay = useCallback(() => {
    setCurrentDate(d => {
      const nd = new Date(d)
      nd.setUTCDate(nd.getUTCDate() + 1)
      return nd
    })
  }, [])

  const handleDatePick = useCallback((dateString) => {
    const parts = dateString.split('-')
    setCurrentDate(new Date(Date.UTC(+parts[0], +parts[1] - 1, +parts[2])))
  }, [])

  const ds = dateStr(currentDate)
  const today = new Date()
  const todayStr = dateStr(new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate())))
  const isToday = ds >= todayStr

  return (
    <div className="app">
      {loading && (
        <div className="loading-overlay">
          <div className="spinner"></div>
        </div>
      )}

      <Header
        currentDate={currentDate}
        currentTab={currentTab}
        isToday={isToday}
        onPrevDay={handlePrevDay}
        onNextDay={handleNextDay}
        onDatePick={handleDatePick}
        onTabChange={setCurrentTab}
      />

      {currentTab === 'daily' && (
        <DailyView
          dateStr={ds}
          onEmpty={setIsEmpty}
          onLoading={setLoading}
        />
      )}

      {currentTab === 'weekly' && (
        <WeeklyView
          dateStr={ds}
          onEmpty={setIsEmpty}
          onLoading={setLoading}
        />
      )}

      {currentTab === 'history' && (
        <BrowsingHistory
          dateStr={ds}
          onEmpty={setIsEmpty}
          onLoading={setLoading}
        />
      )}

      {isEmpty && <EmptyState />}

      <footer className="footer">
        ActivityLens &mdash; All data stays local on your machine. Privacy by design.
      </footer>
    </div>
  )
}

export default App
