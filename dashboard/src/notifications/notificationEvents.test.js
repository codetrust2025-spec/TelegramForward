/**
 * Event → sound: dispatch, dedupe and the mute policy.
 *
 * These run with no React tree at all, which is the point — the sounds must not
 * need a page to be mounted. The audio stub records what was rendered, so the
 * assertions check the sound that actually played, not just a function name.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { installRecordingAudioStub } from './audioTestStub.js'

const policy = { muted: false, buzzerEnabled: true }

vi.mock('../utils/soundQuietHours.js', () => ({
  isMessageSoundMuted: () => policy.muted,
  isInQuietHours: () => policy.muted,
  isQuietHoursEnabled: () => true,
  setQuietHoursEnabled: () => {},
  formatQuietHoursRange: () => '11 PM – 8 AM',
  msUntilQuietHoursEnd: () => 0,
  QUIET_HOURS_START: 23,
  QUIET_HOURS_END: 8,
}))

vi.mock('../utils/replyAlert.js', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, isBuzzerAlertsEnabled: () => policy.buzzerEnabled }
})

const {
  notifyIncomingDm,
  notifyTrackedMail,
  notifyGmailReconnect,
  notifyInterviewReminder,
  notifyIncomingCall,
  notifyCallEnded,
  notifyCallReminder,
  syncUnreadAmbience,
  stopUnreadAmbience,
  __resetNotificationEvents,
} = await import('./notificationEvents.js')

const { playNotification } = await import('./notificationSounds.js')

let audio

beforeEach(() => {
  audio = installRecordingAudioStub()
  policy.muted = false
  policy.buzzerEnabled = true
  __resetNotificationEvents()
  sessionStorage.clear()
  vi.useRealTimers()
})

describe('incoming DM', () => {
  it('sounds once per message and swallows a replay of the same id', () => {
    expect(notifyIncomingDm({ slot: 'a', messageId: 7 })).toBe(true)
    expect(notifyIncomingDm({ slot: 'a', messageId: 7 })).toBe(false)
    expect(notifyIncomingDm({ slot: 'a', messageId: 8 })).toBe(true)
  })

  it('treats the same message id on another account as a different message', () => {
    expect(notifyIncomingDm({ slot: 'a', messageId: 7 })).toBe(true)
    expect(notifyIncomingDm({ slot: 'b', messageId: 7 })).toBe(true)
  })

  it('is silent during quiet hours', () => {
    policy.muted = true
    audio.reset()
    expect(notifyIncomingDm({ slot: 'a', messageId: 1 })).toBe(false)
    expect(audio.record.oscillators).toBe(0)
  })
})

describe('tracked recruitment mail', () => {
  const selection = {
    event: 'notification_created',
    classification: 'offer_received',
    event_id: 'sel-1',
  }
  const booking = {
    event: 'notification_created',
    classification: 'interview_confirmed',
    event_id: 'book-1',
  }

  it('plays the fanfare for a selection and the bell for a booking', () => {
    audio.reset()
    notifyTrackedMail(selection)
    expect([...new Set(audio.record.oscillatorTypes)]).toEqual(['sawtooth'])

    audio.reset()
    notifyTrackedMail(booking)
    expect([...new Set(audio.record.oscillatorTypes)]).toEqual(['sine'])
  })

  it('sounds once per event id however many subscribers deliver it', () => {
    expect(notifyTrackedMail(selection)).toBe(true)
    expect(notifyTrackedMail(selection)).toBe(false)
  })

  it('ignores classifications that are not tracked', () => {
    audio.reset()
    expect(
      notifyTrackedMail({
        event: 'notification_created',
        classification: 'mail_needs_review',
        event_id: 'x',
      }),
    ).toBe(false)
    expect(audio.record.oscillators).toBe(0)
  })

  it('ignores events that are not notification_created', () => {
    expect(
      notifyTrackedMail({ event: 'connected', classification: 'offer_received', event_id: 'y' }),
    ).toBe(false)
  })

  it('still sounds during quiet hours — mail alerts were never muted', () => {
    policy.muted = true
    audio.reset()
    expect(notifyTrackedMail(selection)).toBe(true)
    expect(audio.record.oscillators).toBeGreaterThan(0)
  })
})

describe('gmail reconnect fault', () => {
  it('alerts once per newly disconnected mailbox', () => {
    expect(notifyGmailReconnect([{ id: 1, name: 'A' }])).toBe(true)
    expect(notifyGmailReconnect([{ id: 1, name: 'A' }])).toBe(false)
  })

  it('alerts again for a mailbox that recovered and broke again', () => {
    expect(notifyGmailReconnect([{ id: 1, name: 'A' }])).toBe(true)
    expect(notifyGmailReconnect([])).toBe(false)
    expect(notifyGmailReconnect([{ id: 1, name: 'A' }])).toBe(true)
  })

  it('is not muted by quiet hours', () => {
    policy.muted = true
    expect(notifyGmailReconnect([{ id: 9, name: 'Z' }])).toBe(true)
  })
})

describe('interview reminder', () => {
  it('is not muted by quiet hours', () => {
    policy.muted = true
    audio.reset()
    expect(notifyInterviewReminder()).toBe(true)
    expect(audio.record.oscillators).toBeGreaterThan(0)
  })
})

describe('incoming call', () => {
  it('rings once for a call and ignores repeat ringing frames', () => {
    expect(notifyIncomingCall({ callId: 'c1' })).toBe(true)
    expect(notifyIncomingCall({ callId: 'c1' })).toBe(false)
    notifyCallEnded()
    expect(notifyIncomingCall({ callId: 'c1' })).toBe(true)
    notifyCallEnded()
  })

  it('does not ring during quiet hours', () => {
    policy.muted = true
    expect(notifyIncomingCall({ callId: 'c2' })).toBe(false)
    notifyCallEnded()
  })
})

describe('scheduled call reminder', () => {
  it('does not borrow the incoming-call ring', () => {
    audio.reset()
    notifyIncomingCall({ callId: 'ring' })
    const ringWaveforms = [...new Set(audio.record.oscillatorTypes)]
    notifyCallEnded()

    audio.reset()
    notifyCallReminder('rem-1')
    const reminderWaveforms = [...new Set(audio.record.oscillatorTypes)]
    notifyCallEnded()

    expect(ringWaveforms).toEqual(['sine'])
    expect(reminderWaveforms).toEqual(['triangle'])
  })

  it('sounds once per reminder', () => {
    expect(notifyCallReminder('rem-2')).toBe(true)
    expect(notifyCallReminder('rem-2')).toBe(false)
    notifyCallEnded()
  })

  it('is silenced by the same call-handled path as the ring', () => {
    notifyCallReminder('rem-3')
    notifyCallEnded()
    audio.reset()
    // Nothing further should be scheduled once the loop is stopped.
    expect(audio.record.oscillators).toBe(0)
  })

  it('respects quiet hours, as it did when it shared the ring', () => {
    policy.muted = true
    audio.reset()
    expect(notifyCallReminder('rem-4')).toBe(false)
    expect(audio.record.oscillators).toBe(0)
    notifyCallEnded()
  })
})

describe('unread ambience threshold', () => {
  it('starts above three unread and stops at three or fewer', () => {
    audio.reset()
    syncUnreadAmbience(4, null)
    expect(audio.record.bufferSources).toBeGreaterThan(0)
    stopUnreadAmbience()

    audio.reset()
    syncUnreadAmbience(3, null)
    expect(audio.record.bufferSources).toBe(0)
  })

  it('stays silent during quiet hours', () => {
    policy.muted = true
    audio.reset()
    syncUnreadAmbience(10, null)
    expect(audio.record.bufferSources).toBe(0)
  })
})

describe('CRM buzzer toggle', () => {
  it('gates only the reply SLA tiers', () => {
    policy.buzzerEnabled = false
    expect(playNotification('sla_5')).toBe(false)
    expect(playNotification('sla_10')).toBe(false)
    expect(playNotification('sla_20')).toBe(false)
    // ...and nothing else.
    expect(playNotification('dm')).toBe(true)
    expect(playNotification('mail_selection')).toBe(true)
    expect(playNotification('interview_reminder')).toBe(true)
  })
})
