/**
 * Reply-SLA tiers: thresholds untouched, sounds now independent.
 *
 * The tier *rules* still come from utils/replyAlert.js and are not restated
 * here — what this suite pins is that each tier reaches its own sound, that
 * escalation never leaves two loops running, and that the CRM toggle and quiet
 * hours still silence the whole ladder.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { installRecordingAudioStub } from './audioTestStub.js'

const policy = { muted: false, buzzerEnabled: true }
const state = { level: null, items: [] }

vi.mock('../utils/soundQuietHours.js', () => ({
  isMessageSoundMuted: () => policy.muted,
}))

vi.mock('../utils/replyAlert.js', () => ({
  AGGRESSIVE_BEEP_INTERVAL_MS: 1200,
  BUZZER_BEEP_INTERVAL_MS: 2500,
  REPLY_CHECK_INTERVAL_MS: 30000,
  conversationAlertKey: (conv) => String(conv.id),
  getMaxReplyAlertLevel: () => state.level,
  isBuzzerAlertsEnabled: () => policy.buzzerEnabled,
  listAlertConversations: () => state.items,
}))

const { syncReplyAlertSounds, resetReplyAlertSounds } = await import('./replyAlertSounds.js')
const { isSla10Looping } = await import('./sounds/sla10Pulse.js')
const { isSla20Looping } = await import('./sounds/sla20Siren.js')

let audio

beforeEach(() => {
  audio = installRecordingAudioStub()
  policy.muted = false
  policy.buzzerEnabled = true
  state.level = null
  state.items = []
  resetReplyAlertSounds()
  vi.useRealTimers()
})

describe('tier routing', () => {
  it('plays the marimba once per conversation at the 5-minute tier', () => {
    state.items = [{ level: 'soft', conv: { id: 'c1' } }]
    state.level = 'soft'

    audio.reset()
    syncReplyAlertSounds({})
    // Wooden strike: sine bars plus a noise transient.
    expect(audio.record.bufferSources).toBeGreaterThan(0)
    expect([...new Set(audio.record.oscillatorTypes)]).toEqual(['sine'])

    audio.reset()
    syncReplyAlertSounds({})
    expect(audio.record.oscillators).toBe(0)
  })

  it('runs only the pulse at the 10-minute tier', () => {
    state.level = 'buzzer'
    syncReplyAlertSounds({})
    expect(isSla10Looping()).toBe(true)
    expect(isSla20Looping()).toBe(false)
    resetReplyAlertSounds()
  })

  it('runs only the siren at the 20-minute tier', () => {
    state.level = 'aggressive'
    syncReplyAlertSounds({})
    expect(isSla20Looping()).toBe(true)
    expect(isSla10Looping()).toBe(false)
    resetReplyAlertSounds()
  })

  it('swaps loops on escalation rather than stacking them', () => {
    state.level = 'buzzer'
    syncReplyAlertSounds({})
    expect(isSla10Looping()).toBe(true)

    state.level = 'aggressive'
    syncReplyAlertSounds({})
    expect(isSla10Looping()).toBe(false)
    expect(isSla20Looping()).toBe(true)
    resetReplyAlertSounds()
  })

  it('stops every loop when nothing is overdue', () => {
    state.level = 'aggressive'
    syncReplyAlertSounds({})
    state.level = null
    syncReplyAlertSounds({})
    expect(isSla10Looping()).toBe(false)
    expect(isSla20Looping()).toBe(false)
  })
})

describe('mute policy is unchanged', () => {
  it('silences the ladder when the CRM buzzer toggle is off', () => {
    policy.buzzerEnabled = false
    state.level = 'aggressive'
    state.items = [{ level: 'soft', conv: { id: 'c1' } }]

    audio.reset()
    syncReplyAlertSounds({})
    expect(audio.record.oscillators).toBe(0)
    expect(isSla10Looping()).toBe(false)
    expect(isSla20Looping()).toBe(false)
  })

  it('silences the ladder during quiet hours', () => {
    policy.muted = true
    state.level = 'buzzer'

    audio.reset()
    syncReplyAlertSounds({})
    expect(audio.record.oscillators).toBe(0)
    expect(isSla10Looping()).toBe(false)
  })
})
