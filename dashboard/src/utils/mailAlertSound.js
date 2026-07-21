/**
 * Loud klaxon for tracked mail monitoring alerts (selections + interview booking).
 *
 * Deliberately harsher and longer than the DM chime or the 20-minute interview
 * reminder — these arrive rarely and must not be missed. Rides on the shared
 * AudioContext, so the app-wide unlock click in App.jsx covers it too.
 */

import { getSharedAudioContext } from './notificationSound.js'

/** Candidate got picked — offer/selection/joining mails. */
export const SELECTION_CLASSIFICATIONS = [
  'job_selection_confirmed', 'offer_received', 'offer_accepted', 'joining_confirmed',
]

/** Interview slot movement — booked, moved or dropped. */
export const INTERVIEW_BOOKING_CLASSIFICATIONS = [
  'interview_confirmed', 'interview_rescheduled', 'interview_cancelled',
]

const ALERT_CLASSIFICATIONS = new Set([
  ...SELECTION_CLASSIFICATIONS,
  ...INTERVIEW_BOOKING_CLASSIFICATIONS,
])

export function isTrackedMailAlert(classification) {
  return ALERT_CLASSIFICATIONS.has(String(classification || ''))
}

// The page and the header bell each open their own live socket, so the same
// event arrives twice in one tab. Dedupe here rather than in either component.
const recentEvents = new Map()
const DEDUPE_MS = 8000

function alreadyAlerted(eventId) {
  const now = Date.now()
  for (const [key, at] of recentEvents) {
    if (now - at > DEDUPE_MS) recentEvents.delete(key)
  }
  if (eventId == null) return false
  const key = String(eventId)
  if (recentEvents.has(key)) return true
  recentEvents.set(key, now)
  return false
}

/** One rising klaxon sweep — two detuned saw voices through a bandpass. */
function klaxon(ctx, master, start, lowHz, highHz, dur) {
  const filter = ctx.createBiquadFilter()
  filter.type = 'bandpass'
  filter.Q.setValueAtTime(2.5, start)
  filter.frequency.setValueAtTime(lowHz * 2, start)
  filter.frequency.linearRampToValueAtTime(highHz * 2, start + dur)
  filter.connect(master)

  const swell = ctx.createGain()
  swell.gain.setValueAtTime(0.001, start)
  swell.gain.exponentialRampToValueAtTime(1, start + 0.04)
  swell.gain.setValueAtTime(1, start + dur - 0.06)
  swell.gain.exponentialRampToValueAtTime(0.001, start + dur)
  swell.connect(filter)

  for (const detune of [0, 7]) {
    const osc = ctx.createOscillator()
    osc.type = 'sawtooth'
    osc.detune.setValueAtTime(detune, start)
    osc.frequency.setValueAtTime(lowHz, start)
    osc.frequency.linearRampToValueAtTime(highHz, start + dur)
    osc.connect(swell)
    osc.start(start)
    osc.stop(start + dur + 0.02)
  }
}

/**
 * Play the alert. `urgent` (selections) gets an extra pair of sweeps.
 * Returns true when the sound was actually scheduled.
 */
export function playMailAlertSound({ eventId = null, urgent = false } = {}) {
  if (alreadyAlerted(eventId)) return false
  const ctx = getSharedAudioContext()
  if (!ctx) return false

  const run = () => {
    try {
      const t0 = ctx.currentTime
      const master = ctx.createGain()
      master.gain.setValueAtTime(0.85, t0)
      master.connect(ctx.destination)

      const sweeps = urgent ? 5 : 3
      const gap = 0.42
      for (let i = 0; i < sweeps; i += 1) {
        klaxon(ctx, master, t0 + i * gap, 520, 1180, 0.34)
      }
      // Tail thump so it reads as an alarm rather than a chime.
      klaxon(ctx, master, t0 + sweeps * gap, 320, 240, 0.5)
      master.gain.setValueAtTime(0.85, t0 + sweeps * gap + 0.5)
      master.gain.exponentialRampToValueAtTime(0.001, t0 + sweeps * gap + 0.62)
    } catch {
      /* audio is best-effort */
    }
  }

  if (ctx.state === 'suspended') ctx.resume().then(run).catch(() => {})
  else run()

  try {
    // Phones that ignore background audio still buzz.
    navigator.vibrate?.(urgent ? [300, 120, 300, 120, 300] : [250, 120, 250])
  } catch {
    /* not supported */
  }
  return true
}

/** Desktop notification alongside the sound, so it survives a backgrounded tab. */
export function showMailAlertNotification(payload = {}) {
  if (typeof Notification === 'undefined') return
  if (Notification.permission === 'default') {
    Notification.requestPermission().catch(() => {})
    return
  }
  if (Notification.permission !== 'granted') return
  const title = payload.status
    || String(payload.classification || 'Mail alert').replaceAll('_', ' ')
  const who = payload.candidate_name || 'Candidate'
  const where = payload.company_name ? ` · ${payload.company_name}` : ''
  try {
    new Notification(`📬 ${title}`, {
      body: `${who}${where}`,
      icon: '/favicon.svg',
      tag: `mail-alert-${payload.notification_id || payload.event_id || who}`,
      requireInteraction: true,
    })
  } catch {
    /* ignore */
  }
}
