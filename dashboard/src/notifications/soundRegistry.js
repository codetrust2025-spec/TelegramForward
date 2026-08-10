/**
 * The single catalogue of audible notifications.
 *
 * One entry per notification the product can make a noise about. Each entry
 * owns exactly one sound module, and no two entries may point at the same
 * `play` function — `soundRegistry.test.js` enforces that, which is what stops
 * two notifications from quietly becoming variants of one another again.
 *
 * `quietHours` and `crmToggle` record the mute policy each notification already
 * had before sound delivery was made global; they are not new policy.
 */

import { playDmChime } from './sounds/dmChime.js'
import {
  playUnreadGhostPreview,
  startUnreadGhost,
  stopUnreadGhost,
} from './sounds/unreadGhost.js'
import { startCallRing, stopCallRing } from './sounds/callRing.js'
import { playSla5Marimba } from './sounds/sla5Marimba.js'
import { playSla10Pulse, startSla10Pulse, stopSla10Pulse } from './sounds/sla10Pulse.js'
import { playSla20Siren, startSla20Siren, stopSla20Siren } from './sounds/sla20Siren.js'
import { playInterviewBookingBell } from './sounds/interviewBookingBell.js'
import { playSelectionFanfare } from './sounds/selectionFanfare.js'
import { playGmailFault } from './sounds/gmailFault.js'
import { playInterviewReminder } from './sounds/interviewReminder.js'

export const NOTIFICATION_IDS = [
  'dm',
  'unread_ghost',
  'incoming_call',
  'sla_5',
  'sla_10',
  'sla_20',
  'mail_interview_booking',
  'mail_selection',
  'gmail_reconnect',
  'interview_reminder',
]

/**
 * @typedef {object} SoundEntry
 * @property {string} id
 * @property {string} label      Human name, used by the preview harness.
 * @property {() => boolean} play One-shot render, for previews and tests.
 * @property {(() => boolean)|null} start  Begin a looping sound.
 * @property {(() => void)|null} stop      End a looping sound.
 * @property {boolean} loop
 * @property {boolean} quietHours Muted during quiet hours (pre-existing policy).
 * @property {boolean} crmToggle  Gated by the CRM buzzer toggle (pre-existing).
 * @property {string} dedupe      How repeat delivery of one event is collapsed.
 */

/** @type {Record<string, SoundEntry>} */
export const NOTIFICATION_SOUNDS = {
  dm: {
    id: 'dm',
    label: 'New incoming DM',
    play: playDmChime,
    start: null,
    stop: null,
    loop: false,
    quietHours: true,
    crmToggle: false,
    dedupe: 'slot + message id, 4s window',
  },
  unread_ghost: {
    id: 'unread_ghost',
    label: 'Inbox unread > 3 (ghost ambience)',
    play: playUnreadGhostPreview,
    start: startUnreadGhost,
    stop: stopUnreadGhost,
    loop: true,
    quietHours: true,
    crmToggle: false,
    dedupe: 'state-driven: starts above the threshold, stops at or below it',
  },
  incoming_call: {
    id: 'incoming_call',
    label: 'Incoming voice call',
    play: startCallRing,
    start: startCallRing,
    stop: stopCallRing,
    loop: true,
    quietHours: true,
    crmToggle: false,
    dedupe: 'call id: ringing starts, ended stops; re-ring of a live call ignored',
  },
  sla_5: {
    id: 'sla_5',
    label: 'Reply SLA — 5 minutes',
    play: playSla5Marimba,
    start: null,
    stop: null,
    loop: false,
    quietHours: true,
    crmToggle: true,
    dedupe: 'conversation key, once per conversation while it stays overdue',
  },
  sla_10: {
    id: 'sla_10',
    label: 'Reply SLA — 10 minutes',
    play: playSla10Pulse,
    start: startSla10Pulse,
    stop: stopSla10Pulse,
    loop: true,
    quietHours: true,
    crmToggle: true,
    dedupe: 'tier-driven: one loop while any conversation sits at this tier',
  },
  sla_20: {
    id: 'sla_20',
    label: 'Reply SLA — 20 minutes',
    play: playSla20Siren,
    start: startSla20Siren,
    stop: stopSla20Siren,
    loop: true,
    quietHours: true,
    crmToggle: true,
    dedupe: 'tier-driven: one loop while any conversation sits at this tier',
  },
  mail_interview_booking: {
    id: 'mail_interview_booking',
    label: 'Interview booking mail',
    play: playInterviewBookingBell,
    start: null,
    stop: null,
    loop: false,
    quietHours: false,
    crmToggle: false,
    dedupe: 'mail event id, 8s window across every live socket',
  },
  mail_selection: {
    id: 'mail_selection',
    label: 'Selection / offer mail',
    play: playSelectionFanfare,
    start: null,
    stop: null,
    loop: false,
    quietHours: false,
    crmToggle: false,
    dedupe: 'mail event id, 8s window across every live socket',
  },
  gmail_reconnect: {
    id: 'gmail_reconnect',
    label: 'Gmail reconnect fault',
    play: playGmailFault,
    start: null,
    stop: null,
    loop: false,
    quietHours: false,
    crmToggle: false,
    dedupe: 'mailbox id set, persisted in sessionStorage until it reconnects',
  },
  interview_reminder: {
    id: 'interview_reminder',
    label: 'Interview reminder',
    play: playInterviewReminder,
    start: null,
    stop: null,
    loop: false,
    quietHours: false,
    crmToggle: false,
    dedupe: 'interview id, persisted in sessionStorage for the session',
  },
}

export function soundEntry(id) {
  const entry = NOTIFICATION_SOUNDS[id]
  if (!entry) throw new Error(`Unknown notification sound: ${id}`)
  return entry
}
