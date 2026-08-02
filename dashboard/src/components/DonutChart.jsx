import { useMemo } from 'react'
import { Doughnut } from 'react-chartjs-2'
import { Chart as ChartJS, ArcElement, Tooltip } from 'chart.js'
import { formatDuration } from '../api'

ChartJS.register(ArcElement, Tooltip)

export default function DonutChart({ summary }) {
  const byCat = summary?.by_category || {}
  const prodSecs = byCat.productive?.seconds || 0
  const neutralSecs = byCat.neutral?.seconds || 0
  const distractSecs = byCat.distracting?.seconds || 0
  const activeSecs = prodSecs + neutralSecs + distractSecs

  const data = useMemo(() => ({
    labels: ['Productive', 'Neutral', 'Distracting'],
    datasets: [{
      data: [prodSecs, neutralSecs, distractSecs],
      backgroundColor: ['#34d399', '#fbbf24', '#f87171'],
      borderColor: 'transparent',
      borderWidth: 0,
      hoverOffset: 6,
    }],
  }), [prodSecs, neutralSecs, distractSecs])

  const options = useMemo(() => ({
    responsive: true,
    maintainAspectRatio: true,
    cutout: '72%',
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: '#1a1d2e',
        borderColor: 'rgba(255,255,255,0.1)',
        borderWidth: 1,
        titleColor: '#e8eaf0',
        bodyColor: '#8b8fa3',
        padding: 10,
        callbacks: {
          label: (ctx) => `${ctx.label}: ${formatDuration(ctx.raw)}`,
        },
      },
    },
    animation: { animateRotate: true, duration: 800 },
  }), [])

  return (
    <div className="donut-wrapper" style={{ position: 'relative', maxHeight: 280 }}>
      <Doughnut data={data} options={options} />
      <div className="donut-center">
        <div className="donut-value">{formatDuration(activeSecs)}</div>
        <div className="donut-label">Active</div>
      </div>
    </div>
  )
}
