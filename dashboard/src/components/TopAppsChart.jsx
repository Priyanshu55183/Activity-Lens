import { useMemo } from 'react'
import { Bar } from 'react-chartjs-2'
import {
  Chart as ChartJS, CategoryScale, LinearScale, BarElement, Tooltip,
} from 'chart.js'
import { categoryColor } from '../api'

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip)

export default function TopAppsChart({ apps }) {
  const top = apps.slice(0, 8)

  const data = useMemo(() => {
    const labels = top.map(a => a.name.length > 25 ? a.name.slice(0, 22) + '...' : a.name)
    const values = top.map(a => a.seconds / 60)
    const colors = top.map(a => categoryColor(a.category))

    return {
      labels,
      datasets: [{
        data: values,
        backgroundColor: colors.map(c => c + '33'),
        borderColor: colors,
        borderWidth: 1.5,
        borderRadius: 4,
        barPercentage: 0.7,
      }],
    }
  }, [top])

  const options = useMemo(() => ({
    responsive: true,
    maintainAspectRatio: true,
    indexAxis: 'y',
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: '#1a1d2e',
        borderColor: 'rgba(255,255,255,0.1)',
        borderWidth: 1,
        callbacks: { label: (ctx) => `${Math.round(ctx.raw)} min` },
      },
    },
    scales: {
      x: {
        grid: { color: 'rgba(255,255,255,0.04)' },
        ticks: { color: '#5c5f73', font: { size: 11 } },
        title: { display: true, text: 'Minutes', color: '#5c5f73', font: { size: 11 } },
      },
      y: {
        grid: { display: false },
        ticks: { color: '#8b8fa3', font: { size: 11 } },
      },
    },
    animation: { duration: 600 },
  }), [])

  if (top.length === 0) return <div style={{ color: 'var(--text-muted)', padding: 24 }}>No data</div>

  return (
    <div className="chart-container" style={{ maxHeight: 280 }}>
      <Bar data={data} options={options} />
    </div>
  )
}
