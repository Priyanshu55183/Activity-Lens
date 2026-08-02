import { useMemo } from 'react'
import { Line } from 'react-chartjs-2'
import {
  Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement,
  Filler, Tooltip,
} from 'chart.js'
import { dayName } from '../api'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Filler, Tooltip)

export default function TrendChart({ days }) {
  const labels = days.map(d => dayName(d.date))

  const prodPcts = days.map(d => {
    const byCat = d.by_category || {}
    const idleSecs = byCat.idle?.seconds || 0
    const activeSecs = d.total_seconds - idleSecs
    const prodSecs = byCat.productive?.seconds || 0
    return activeSecs > 0 ? Math.round((prodSecs / activeSecs) * 100) : 0
  })

  const data = useMemo(() => ({
    labels,
    datasets: [{
      label: 'Productive %',
      data: prodPcts,
      borderColor: '#34d399',
      backgroundColor: (context) => {
        const chart = context.chart
        const { ctx, chartArea } = chart
        if (!chartArea) return 'transparent'
        const gradient = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom)
        gradient.addColorStop(0, 'rgba(52, 211, 153, 0.25)')
        gradient.addColorStop(1, 'rgba(52, 211, 153, 0.01)')
        return gradient
      },
      fill: true,
      tension: 0.4,
      borderWidth: 2.5,
      pointRadius: 5,
      pointBackgroundColor: '#34d399',
      pointBorderColor: '#0f1117',
      pointBorderWidth: 2,
      pointHoverRadius: 7,
    }],
  }), [labels, prodPcts])

  const options = useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: '#1a1d2e',
        borderColor: 'rgba(255,255,255,0.1)',
        borderWidth: 1,
        callbacks: { label: (ctx) => `${ctx.raw}% productive` },
      },
    },
    scales: {
      y: {
        min: 0, max: 100,
        grid: { color: 'rgba(255,255,255,0.04)' },
        ticks: { color: '#5c5f73', font: { size: 11 }, callback: v => v + '%' },
      },
      x: {
        grid: { display: false },
        ticks: { color: '#8b8fa3', font: { size: 12 } },
      },
    },
    animation: { duration: 800 },
  }), [])

  return <Line data={data} options={options} />
}
