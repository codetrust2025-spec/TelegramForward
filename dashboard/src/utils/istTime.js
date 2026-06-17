/**
 * All user-visible dates/times use India Standard Time (Asia/Kolkata).
 * Storage remains UTC ISO / unix; only display is localized to IST.
 */

export const IST_TIMEZONE = 'Asia/Kolkata'
export const IST_LOCALE = 'en-IN'

const DEFAULT_DATE_TIME = {
  timeZone: IST_TIMEZONE,
  day: '2-digit',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hour12: true,
}

/** Parse ISO, unix sec/ms, or legacy "YYYY-MM-DD HH:MM UTC|IST" strings. */
export function parseInstant(value) {
  if (value == null || value === '') return null
  if (typeof value === 'number') {
    const ms = value < 1e12 ? value * 1000 : value
    const d = new Date(ms)
    return Number.isNaN(d.getTime()) ? null : d
  }
  const text = String(value).trim()
  if (!text) return null
  if (/^\d{2}:\d{2}:\d{2}$/.test(text)) return null
  if (text.endsWith(' UTC')) {
    const iso = text.replace(' UTC', ':00Z').replace(' ', 'T')
    const d = new Date(iso)
    return Number.isNaN(d.getTime()) ? null : d
  }
  if (text.endsWith(' IST')) {
    const iso = text.replace(' IST', '+05:30').replace(' ', 'T')
    const d = new Date(iso)
    return Number.isNaN(d.getTime()) ? null : d
  }
  const d = new Date(text)
  return Number.isNaN(d.getTime()) ? null : d
}

export function formatIstDateTime(value, options = {}) {
  const d = parseInstant(value)
  if (!d) return '—'
  return d.toLocaleString(IST_LOCALE, {
    ...DEFAULT_DATE_TIME,
    ...options,
    timeZone: IST_TIMEZONE,
  })
}

export function formatIstTime(value, options = {}) {
  const d = parseInstant(value)
  if (!d) return '—'
  return d.toLocaleTimeString(IST_LOCALE, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
    timeZone: IST_TIMEZONE,
    ...options,
  })
}

export function formatIstDate(value, options = {}) {
  const d = parseInstant(value)
  if (!d) return '—'
  return d.toLocaleDateString(IST_LOCALE, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone: IST_TIMEZONE,
    ...options,
  })
}

/** Short: Jun 3, 10:28 am (no year if same calendar year optional via caller) */
export function formatIstShort(value) {
  const d = parseInstant(value)
  if (!d) return '—'
  return d.toLocaleString(IST_LOCALE, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
    timeZone: IST_TIMEZONE,
  })
}

/** Logs / timeline — 24h clock in IST */
export function formatIstLogTime(time) {
  if (!time) return '--:--:--'
  if (typeof time === 'string' && /^\d{2}:\d{2}:\d{2}$/.test(time)) return `${time} IST`
  const d = parseInstant(time)
  if (!d) return String(time)
  return formatIstTime(d)
}

/** Relative age label; absolute part in IST when > 48h */
/** YYYY-MM-DD in IST — for same-day comparisons in inbox UI */
export function istDayKey(value = new Date()) {
  const d = parseInstant(value) ?? new Date()
  return d.toLocaleDateString(IST_LOCALE, {
    timeZone: IST_TIMEZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
}

export function formatIstAge(value) {
  const d = parseInstant(value)
  if (!d) return null
  const mins = Math.floor((Date.now() - d.getTime()) / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 48) return `${hrs}h ago`
  return formatIstDate(d, { year: undefined })
}
