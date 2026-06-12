const IST_OFFSET_MS = (5 * 60 + 30) * 60 * 1000

export function parseInstant(value) {
  if (!value) return null
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? null : d
}

export function toIstDate(date) {
  const d = date instanceof Date ? date : parseInstant(date)
  if (!d) return null
  return new Date(d.getTime() + IST_OFFSET_MS)
}

export function istDayKey(date = new Date()) {
  const d = toIstDate(date)
  if (!d) return ''
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}-${String(d.getUTCDate()).padStart(2, '0')}`
}

export function formatIstDate(date, options = {}) {
  const d = toIstDate(date)
  if (!d) return ''
  return d.toLocaleDateString('en-IN', { timeZone: 'UTC', ...options })
}

export function formatIstDateTime(value) {
  const d = parseInstant(value)
  if (!d) return ''
  return d.toLocaleString('en-IN', {
    timeZone: 'Asia/Kolkata',
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}
