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
  'job_selection_confirmed', 'offer_received', 'offer_accepted',
  'offer_declined', 'offer_revoked', 'joining_confirmed',
  'joining_date_updated', 'onboarding_started', 'background_verification',
  'document_verification', 'compensation_confirmation',
  'candidate_rejected',
]

/** Interview slot movement — booked, moved or dropped. */
export const INTERVIEW_BOOKING_CLASSIFICATIONS = [
  'interview_shortlisted', 'interview_confirmed', 'interview_rescheduled',
  'interview_cancelled',
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
 * A fixed-pitch descending digital fault signal for expired Gmail credentials.
 *
 * This deliberately avoids the rising, sweeping sawtooth used for mail events:
 * three short square-wave notes descend twice, with a clear pause between each
 * group. Admins can therefore identify a broken mailbox without looking at the
 * screen.
 */
function reconnectFaultPulse(ctx, master, start, frequency, dur = 0.16) {
  const gain = ctx.createGain()
  gain.gain.setValueAtTime(0.001, start)
  gain.gain.exponentialRampToValueAtTime(0.7, start + 0.015)
  gain.gain.setValueAtTime(0.7, start + dur - 0.025)
  gain.gain.exponentialRampToValueAtTime(0.001, start + dur)
  gain.connect(master)

  const osc = ctx.createOscillator()
  osc.type = 'square'
  osc.frequency.setValueAtTime(frequency, start)
  osc.connect(gain)
  osc.start(start)
  osc.stop(start + dur + 0.02)
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

/**
 * Play the Gmail reconnect-required signal.
 *
 * Kept separate from `playMailAlertSound` so credential failures can never
 * sound like a selection, offer or interview notification.
 */
export function playGmailReconnectAlertSound({ eventId = null } = {}) {
  if (alreadyAlerted(eventId)) return false
  const ctx = getSharedAudioContext()
  if (!ctx) return false

  const run = () => {
    try {
      const t0 = ctx.currentTime
      const master = ctx.createGain()
      master.gain.setValueAtTime(0.72, t0)
      master.connect(ctx.destination)

      const notes = [880, 440, 220]
      for (const groupOffset of [0, 0.9]) {
        notes.forEach((frequency, index) => {
          reconnectFaultPulse(
            ctx,
            master,
            t0 + groupOffset + index * 0.22,
            frequency,
          )
        })
      }
      master.gain.setValueAtTime(0.72, t0 + 1.5)
      master.gain.exponentialRampToValueAtTime(0.001, t0 + 1.62)
    } catch {
      /* audio is best-effort */
    }
  }

  if (ctx.state === 'suspended') ctx.resume().then(run).catch(() => {})
  else run()

  try {
    navigator.vibrate?.([500, 180, 120, 180, 500])
  } catch {
    /* not supported */
  }
  return true
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** '2026-08-04' -> '4 Aug 2026'. Empty when there is no usable day. */
export function notificationDate(value) {
  const parts = String(value || '').trim().slice(0, 10).split('-')
  if (parts.length !== 3 || !parts.every((p) => /^\d+$/.test(p))) return ''
  const [year, month, day] = parts.map(Number)
  if (month < 1 || month > 12) return ''
  return `${day} ${MONTHS[month - 1]} ${year}`
}

/** '17:00' -> '5:00 PM'. Accepts the 12-hour form the model emits too. */
export function notificationTime(value) {
  let clock = String(value || '').trim().toUpperCase()
  let suffix = ''
  for (const meridiem of ['AM', 'PM']) {
    if (clock.endsWith(meridiem)) {
      suffix = meridiem
      clock = clock.slice(0, -2).trim()
      break
    }
  }
  const [rawHour, rawMinute] = clock.split(':')
  if (!/^\d+$/.test(rawHour || '') || !/^\d+$/.test(rawMinute || '')) return ''
  const hour = Number(rawHour)
  const minute = Number(rawMinute)
  if (minute > 59) return ''
  if (suffix) {
    return hour >= 1 && hour <= 12 ? `${hour}:${String(minute).padStart(2, '0')} ${suffix}` : ''
  }
  if (hour > 23) return ''
  return `${hour % 12 || 12}:${String(minute).padStart(2, '0')} ${hour < 12 ? 'AM' : 'PM'}`
}

/**
 * One booking, one notification. Keyed on the booking so a retried delivery
 * replaces its predecessor instead of stacking another copy of the same news.
 */
function bookingTag(payload) {
  const key = payload.booking_id
    || payload.booking_audit_id
    || payload.notification_id
    || payload.event_id
    || payload.candidate_name
  return `interview-booking-${key}`
}

/**
 * What a booking notification should say.
 *
 * Each line is omitted rather than shown half-empty: "undefined · undefined"
 * is worse than a line that only names the candidate. Separate from delivery
 * so the wording can be tested without a Notification implementation.
 */
export function buildBookingNotification(payload = {}) {
  const who = String(payload.candidate_name || '').trim()
  if (!who) return null
  const company = String(payload.company_name || '').trim()
  const day = notificationDate(payload.interview_date)
  const start = notificationTime(payload.start_time || payload.interview_time)
  const end = notificationTime(payload.end_time)
  const round = String(payload.interview_round || '').trim()
  const status = String(payload.status || '').toLowerCase()
  const event = String(payload.event || '')

  const span = start && end ? `${start}–${end}` : start
  const when = [day, span].filter(Boolean).join(' · ')
  const lines = [[who, company].filter(Boolean).join(' · ')]
  const tag = bookingTag(payload)

  if (event === 'slot_booking_blocked' || status === 'blocked') {
    // The blocked case names the time that was refused, then why.
    const reason = String(payload.block_reason || '').trim()
    return {
      title: 'Automatic Booking Blocked',
      body: [[who, day, start].filter(Boolean).join(' · '),
             reason ? `Reason: ${reason}` : null].filter(Boolean).join('\n'),
      tag,
    }
  }
  if (event === 'interview_rescheduled' || status === 'rescheduled') {
    if (when) lines.push(`Changed to ${when}`)
    return { title: 'Interview Rescheduled', body: lines.join('\n'), tag }
  }
  if (when) lines.push(when)
  if (round) lines.push(`Round: ${round}`)
  return { title: 'Interview Auto-Booked', body: lines.join('\n'), tag }
}

const BOOKING_EVENTS = new Set([
  'slot_auto_booked', 'slot_manually_booked', 'interview_rescheduled', 'slot_booking_blocked',
])

/** Desktop notification alongside the sound, so it survives a backgrounded tab. */
export function showMailAlertNotification(payload = {}) {
  if (typeof Notification === 'undefined') return
  if (Notification.permission === 'default') {
    Notification.requestPermission().catch(() => {})
    return
  }
  if (Notification.permission !== 'granted') return

  // A booking has a confirmed schedule behind it, so it says what and when
  // rather than the generic wording that made every booking look identical.
  const booking = BOOKING_EVENTS.has(String(payload.event || ''))
    ? buildBookingNotification(payload)
    : null
  if (booking) {
    try {
      const note = new Notification(`📅 ${booking.title}`, {
        body: booking.body,
        icon: '/favicon.svg',
        tag: booking.tag,
        requireInteraction: true,
        data: { url: payload.booking_url || '', candidateId: payload.candidate_id || '' },
      })
      note.onclick = () => {
        // Raising the window is a courtesy and some environments refuse it;
        // that must not stop the click from opening the booking.
        try {
          window.focus?.()
        } catch {
          /* not permitted here */
        }
        try {
          window.dispatchEvent(new CustomEvent('teleautomation:navigate', {
            detail: payload.booking_id
              ? { view: 'daily-ops', bookingId: payload.booking_id, candidateId: payload.candidate_id }
              : { view: 'candidates', candidateId: payload.candidate_id },
          }))
          note.close?.()
        } catch {
          /* informational notification; navigation is best effort */
        }
      }
    } catch {
      /* ignore */
    }
    return
  }

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
