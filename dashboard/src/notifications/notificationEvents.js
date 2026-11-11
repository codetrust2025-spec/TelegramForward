/**
 * Event → sound. The only place that decides which notification a raw event is.
 *
 * Transports (WebSockets, polls) call in here; they never reach the sound
 * modules directly. Dedupe lives here too, so an event replayed by a socket
 * reconnect or delivered to two subscribers is still heard once.
 */

import {
  SELECTION_CLASSIFICATIONS,
  isTrackedMailAlert,
  showMailAlertNotification,
} from '../utils/mailAlertSound.js'
import { describeReconnectTargets } from '../utils/mailboxStatus.js'
import { getMaxReplyAlertLevel } from '../utils/replyAlert.js'
import { isMessageSoundMuted } from '../utils/soundQuietHours.js'
import { playNotification, startNotification, stopNotification } from './notificationSounds.js'

/* ── new incoming DM ─────────────────────────────────────────────────── */

const DM_DEDUPE_MS = 4000
const recentDms = new Map()

/** True the first time this message is seen; false for a replay within 4s. */
function firstSightOfDm(slot, messageId) {
  if (messageId == null) return true
  const key = `${slot}:${messageId}`
  const now = Date.now()
  const last = recentDms.get(key)
  if (last != null && now - last < DM_DEDUPE_MS) return false
  recentDms.set(key, now)
  for (const [k, at] of recentDms) {
    if (now - at > DM_DEDUPE_MS * 2) recentDms.delete(k)
  }
  return true
}

export function notifyIncomingDm({ slot = '', messageId } = {}) {
  if (!firstSightOfDm(slot, messageId)) return false
  return playNotification('dm')
}

/* ── incoming voice call ─────────────────────────────────────────────── */

let ringingCallId = null

/** Ring for a newly ringing call; ignore repeat frames for the same call. */
export function notifyIncomingCall({ callId = null } = {}) {
  const key = callId == null ? 'unknown' : String(callId)
  if (ringingCallId === key) return false
  ringingCallId = key
  return startNotification('incoming_call')
}

/**
 * Silence the call sounds.
 *
 * Stops the reminder as well as the ring. Before these were separate sounds,
 * one stop covered both because they were literally the same loop; keeping
 * that lifecycle means the existing "call handled" paths still leave the app
 * quiet rather than stranding a reminder ringing behind a dismissed modal.
 */
export function notifyCallEnded() {
  ringingCallId = null
  stopNotification('incoming_call')
  stopNotification('call_reminder')
}

/* ── scheduled call reminder ─────────────────────────────────────────── */

/**
 * A scheduled call has come due.
 *
 * This has its own sound rather than borrowing the incoming-call ring. The two
 * events ask for opposite things — a call arriving must be answered now, a
 * reminder means you owe someone a call — and a shared ring made a reminder
 * indistinguishable from a live call until you looked at the screen.
 */
const alertedReminders = new Set()

export function notifyCallReminder(reminderId) {
  const key = String(reminderId ?? 'unknown')
  if (alertedReminders.has(key)) return false
  alertedReminders.add(key)
  return startNotification('call_reminder')
}

export function stopCallReminder() {
  stopNotification('call_reminder')
}

/* ── inbox unread ambience ───────────────────────────────────────────── */

const UNREAD_MUSIC_THRESHOLD = 3

/**
 * Start or stop the ghost ambience from the unread count.
 *
 * Threshold and the deference to a live SLA tier are unchanged: the horror bed
 * would otherwise play underneath the reply buzzer and neither would be legible.
 */
export function syncUnreadAmbience(unreadCount, inboxState = null) {
  if (isMessageSoundMuted()) {
    stopNotification('unread_ghost')
    return
  }
  const slaLevel = inboxState ? getMaxReplyAlertLevel(inboxState) : null
  if (slaLevel === 'buzzer' || slaLevel === 'aggressive') {
    stopNotification('unread_ghost')
    return
  }
  const count = Math.max(0, Number(unreadCount) || 0)
  if (count > UNREAD_MUSIC_THRESHOLD) startNotification('unread_ghost')
  else stopNotification('unread_ghost')
}

export function stopUnreadAmbience() {
  stopNotification('unread_ghost')
}

/* ── tracked recruitment mail ────────────────────────────────────────── */

const MAIL_DEDUPE_MS = 8000
const recentMailEvents = new Map()

function firstSightOfMailEvent(eventId) {
  const now = Date.now()
  for (const [key, at] of recentMailEvents) {
    if (now - at > MAIL_DEDUPE_MS) recentMailEvents.delete(key)
  }
  if (eventId == null) return true
  const key = String(eventId)
  if (recentMailEvents.has(key)) return false
  recentMailEvents.set(key, now)
  return true
}

/**
 * Sound a tracked recruitment mail.
 *
 * Selections and interview bookings now have entirely separate sounds — a
 * fanfare and a bell — where they used to be a five-sweep and a three-sweep
 * variant of the same klaxon. Which classifications belong to which group is
 * unchanged.
 */
export function notifyTrackedMail(payload) {
  if (payload?.event !== 'notification_created') return false
  const classification = payload?.classification
  if (!isTrackedMailAlert(classification)) return false
  if (!firstSightOfMailEvent(payload.event_id || payload.notification_id)) return false

  const selection = SELECTION_CLASSIFICATIONS.includes(classification)
  const played = playNotification(selection ? 'mail_selection' : 'mail_interview_booking')

  try {
    navigator.vibrate?.(selection ? [300, 120, 300, 120, 300] : [250, 120, 250])
  } catch {
    /* not supported */
  }

  showMailAlertNotification(payload)
  return played
}

/* ── Gmail credential fault ──────────────────────────────────────────── */

const GMAIL_ALERTED_KEY = 'teleautomation:gmail-reconnect-alerted'

function readAlertedMailboxIds() {
  try {
    return new Set(JSON.parse(sessionStorage.getItem(GMAIL_ALERTED_KEY) || '[]').map(String))
  } catch {
    return new Set()
  }
}

function writeAlertedMailboxIds(ids) {
  try {
    sessionStorage.setItem(GMAIL_ALERTED_KEY, JSON.stringify(ids.map(String)))
  } catch {
    /* session storage is optional */
  }
}

/**
 * Alert once per mailbox that has newly fallen into RECONNECT_REQUIRED.
 *
 * The alerted set is rewritten to the current disconnected set every pass, so a
 * mailbox that reconnects and breaks again alerts a second time — matching the
 * behaviour the recruitment page had.
 *
 * @param {Array<{id: string|number, name?: string}>} disconnected
 */
export function notifyGmailReconnect(disconnected) {
  const alerted = readAlertedMailboxIds()
  const newly = disconnected.filter((row) => !alerted.has(String(row.id)))

  if (newly.length) {
    // Count the mailboxes, not the subset that happens to carry a name. The
    // health payload has no name column, so filtering to named rows collapsed
    // every real alert to "0 candidate accounts" while the dashboard listed
    // the same mailboxes as Reconnect Required.
    const summary = describeReconnectTargets(newly)
    const eventId = `gmail-reconnect-${newly.map((row) => String(row.id)).sort().join('-')}`
    playNotification('gmail_reconnect')
    try {
      navigator.vibrate?.([500, 180, 120, 180, 500])
    } catch {
      /* not supported */
    }
    showMailAlertNotification({
      status: 'Gmail connection expired',
      candidate_name: summary,
      notification_id: eventId,
    })
  }

  writeAlertedMailboxIds(disconnected.map((row) => row.id))
  return newly.length > 0
}

/* ── interview reminder ──────────────────────────────────────────────── */

export function notifyInterviewReminder() {
  return playNotification('interview_reminder')
}

/** Test seam: clear every dedupe memory. */
export function __resetNotificationEvents() {
  recentDms.clear()
  recentMailEvents.clear()
  alertedReminders.clear()
  ringingCallId = null
}
