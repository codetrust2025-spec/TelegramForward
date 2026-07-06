/**
 * Browser notification 20 minutes before each upcoming interview.
 * Polls the upcoming interviews API every 5 minutes and schedules
 * notifications for any interview starting within the next 25 minutes.
 */
import { useEffect, useRef } from 'react'
import { useAuth } from '../context/AuthContext.jsx'

const API = typeof window !== 'undefined' && window.location.port === '3000'
  ? '' : (typeof window !== 'undefined' ? `${window.location.protocol}//${window.location.host}` : '')

const NOTIFY_BEFORE_MS = 20 * 60 * 1000 // 20 minutes
const POLL_INTERVAL_MS = 5 * 60 * 1000  // check every 5 minutes
const NOTIFIED_KEY = 'interview_notified_ids'

function getNotifiedIds() {
  try {
    return new Set(JSON.parse(sessionStorage.getItem(NOTIFIED_KEY) || '[]'))
  } catch { return new Set() }
}

function markNotified(id) {
  const ids = getNotifiedIds()
  ids.add(id)
  // Keep only last 50 to avoid bloat
  const arr = [...ids].slice(-50)
  sessionStorage.setItem(NOTIFIED_KEY, JSON.stringify(arr))
}

function requestPermission() {
  if (!('Notification' in window)) return
  if (Notification.permission === 'default') {
    Notification.requestPermission()
  }
}

function sendNotification(interview) {
  if (!('Notification' in window) || Notification.permission !== 'granted') return

  const name = interview.name || 'Unknown'
  const round = interview.interview_round || ''
  const tech = interview.technology || ''
  const time = interview.time || ''

  const timeStr = time ? formatTime(time) : ''
  const body = [round, tech, timeStr].filter(Boolean).join(' · ')

  try {
    new Notification(`⏰ Interview in 20 min: ${name}`, {
      body: body || 'Upcoming interview',
      icon: '/favicon.svg',
      tag: `interview-${interview.id || name}`,
      requireInteraction: true,
    })
  } catch (e) {
    console.warn('Notification failed:', e)
  }
}

function formatTime(hhmm) {
  if (!hhmm) return ''
  const [h, m] = hhmm.split(':').map(Number)
  if (isNaN(h)) return hhmm
  const d = new Date()
  d.setHours(h, m || 0, 0, 0)
  return d.toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit', hour12: true })
}

function parseInterviewDateTime(interview) {
  const date = interview.date || ''
  const time = interview.time || ''
  if (!date || !time) return null
  try {
    const [h, m] = time.split(':').map(Number)
    const dt = new Date(`${date}T${String(h).padStart(2, '0')}:${String(m || 0).padStart(2, '0')}:00`)
    if (isNaN(dt.getTime())) return null
    return dt
  } catch { return null }
}

export function useInterviewNotifications() {
  const { authenticated } = useAuth()
  const timerRef = useRef(null)

  useEffect(() => {
    if (!authenticated) return
    requestPermission()

    async function checkAndNotify() {
      try {
        const params = new URLSearchParams({ days: '1', include_today: 'true' })
        const res = await fetch(`${API}/candidates/interviews/upcoming?${params}`, { credentials: 'include' })
        if (!res.ok) return
        const data = await res.json()
        if (data.status !== 'ok') return

        const interviews = data.interviews || []
        const now = Date.now()
        const notified = getNotifiedIds()

        for (const interview of interviews) {
          const id = interview.id || `${interview.name}-${interview.date}-${interview.time}`
          if (notified.has(id)) continue

          const startTime = parseInterviewDateTime(interview)
          if (!startTime) continue

          const diff = startTime.getTime() - now
          // Notify if interview is 15-25 minutes away (window around 20 min)
          if (diff > 0 && diff <= 25 * 60 * 1000 && diff >= 15 * 60 * 1000) {
            sendNotification(interview)
            markNotified(id)
          }
          // Also notify if interview is 0-5 minutes away and wasn't notified yet
          if (diff > 0 && diff <= 5 * 60 * 1000) {
            sendNotification({ ...interview, _imminent: true })
            markNotified(id)
          }
        }
      } catch (e) {
        console.warn('Interview notification check failed:', e)
      }
    }

    // Initial check
    checkAndNotify()

    // Poll every 5 minutes
    timerRef.current = setInterval(checkAndNotify, POLL_INTERVAL_MS)

    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [authenticated])
}
