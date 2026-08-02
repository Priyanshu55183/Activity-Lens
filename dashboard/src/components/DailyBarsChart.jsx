import { useMemo } from 'react'
import { Bar } from 'react-chartjs-2'
import {
  Chart as ChartJS, CategoryScale, LinearScale, BarElement, Tooltip, Legend,
} from 'chart.js'
import { dayName } from '../api'

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend)

export default function DailyBarsChart({ days }) {
  const labels = days.map(d => dayName(d.date))

  const data = useMemo(() => ({
    labels,
    datasets: [
      {
        label: 'Productive',
        data: days.map(d => (d.by_category?.productive?.seconds || 0) / 3600),
        backgroundColor: '#34d39966',
        borderColor: '#34d399',
        borderWidth: 1,
        borderRadius: 3,
      },
      {
        label: 'Neutral',
        data: days.map(d => (d.by_category?.neutral?.seconds || 0) / 3600),
        backgroundColor: '#fbbf2466',
        borderColor: '#fbbf24',
        borderWidth: 1,
        borderRadius: 3,
      },
      {
        label: 'Distracting',
        data: days.map(d => (d.by_category?.distracting?.seconds || 0) / 3600),
        backgroundColor: '#f8717166',
        borderColor: '#f87171',
        borderWidth: 1,
        borderRadius: 3,
      },
    ],
  }), [labels, days])

  const options = useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: true,
        position: 'bottom',
        labels: {
          color: '#8b8fa3', font: { size: 11 },
          usePointStyle: true, pointStyle: 'circle', padding: 16,
        },
      },
      tooltip: {
        backgroundColor: '#1a1d2e',
        borderColor: 'rgba(255,255,255,0.1)',
        borderWidth: 1,
        callbacks: { label: (ctx) => `${ctx.dataset.label}: ${ctx.raw.toFixed(1)}h` },
      },
    },
    scales: {
      x: {
        stacked: true,
        grid: { display: false },
        ticks: { color: '#8b8fa3', font: { size: 12 } },
      },
      y: {
        stacked: true,
        grid: { color: 'rgba(255,255,255,0.04)' },
        ticks: { color: '#5c5f73', font: { size: 11 }, callback: v => v + 'h' },
        title: { display: true, text: 'Hours', color: '#5c5f73', font: { size: 11 } },
      },
    },
    animation: { duration: 600 },
  }), [])

  return <Bar data={data} options={options} />
}
