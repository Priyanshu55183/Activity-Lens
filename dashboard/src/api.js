// API helper functions

const BASE = '';  // proxy handles /api in dev, same-origin in prod

export async function fetchJSON(url) {
  const resp = await fetch(`${BASE}${url}`);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json();
}

export function dateStr(d) {
  return d.toISOString().slice(0, 10);
}

export function formatDuration(seconds) {
  if (!seconds || seconds < 0) return '0m';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}h ${String(m).padStart(2, '0')}m`;
  return `${m}m`;
}

export function formatTime(isoStr) {
  if (!isoStr) return '--:--';
  return isoStr.slice(11, 16);
}

export function categoryColor(cat) {
  const colors = {
    productive: '#34d399',
    neutral: '#fbbf24',
    distracting: '#f87171',
    idle: '#475569',
  };
  return colors[cat] || '#8b8fa3';
}

export function dayName(dateString) {
  const d = new Date(dateString + 'T12:00:00');
  return d.toLocaleDateString('en-US', { weekday: 'short' });
}

export async function fetchBrowsingHistory(dateStr) {
  return fetchJSON(`/api/history/${dateStr}`);
}

export async function fetchRecentSites() {
  return fetchJSON('/api/recent-sites');
}

export async function fetchSessionDetail(sessionId) {
  return fetchJSON(`/api/session/${sessionId}`);
}
