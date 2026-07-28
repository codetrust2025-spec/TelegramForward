import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  isTrackedMailAlert,
  playGmailReconnectAlertSound,
  playMailAlertSound,
} from './mailAlertSound.js'

// notificationSound.js caches the AudioContext for the whole module lifetime, so
// the stub is installed once and this array is shared by every test.
const started = []

/** Minimal Web Audio stub — records how many oscillators got started. */
function installAudioStub() {
  const node = () => ({
    connect: vi.fn(),
    gain: { setValueAtTime: vi.fn(), exponentialRampToValueAtTime: vi.fn(), linearRampToValueAtTime: vi.fn() },
    frequency: { setValueAtTime: vi.fn(), linearRampToValueAtTime: vi.fn() },
    Q: { setValueAtTime: vi.fn() },
    detune: { setValueAtTime: vi.fn() },
    start: vi.fn(function start(at) { started.push(at) }),
    stop: vi.fn(),
  })
  window.AudioContext = vi.fn(() => ({
    state: 'running',
    currentTime: 0,
    destination: {},
    createGain: node,
    createOscillator: node,
    createBiquadFilter: node,
  }))
}

describe('mail alert sound', () => {
  beforeEach(() => { installAudioStub(); started.length = 0 })
  afterEach(() => { vi.useRealTimers() })

  it('tracks selection and interview booking classifications only', () => {
    expect(isTrackedMailAlert('job_selection_confirmed')).toBe(true)
    expect(isTrackedMailAlert('interview_confirmed')).toBe(true)
    expect(isTrackedMailAlert('interview_cancelled')).toBe(true)
    expect(isTrackedMailAlert('mail_needs_review')).toBe(false)
    expect(isTrackedMailAlert('')).toBe(false)
    expect(isTrackedMailAlert(undefined)).toBe(false)
  })

  it('plays once per event even when both live sockets deliver it', () => {
    expect(playMailAlertSound({ eventId: 'evt-1' })).toBe(true)
    expect(playMailAlertSound({ eventId: 'evt-1' })).toBe(false)
    expect(playMailAlertSound({ eventId: 'evt-2' })).toBe(true)
  })

  it('gives selections a longer burst than interview bookings', () => {
    playMailAlertSound({ eventId: 'normal', urgent: false })
    const normal = started.length
    started.length = 0
    playMailAlertSound({ eventId: 'urgent', urgent: true })
    expect(started.length).toBeGreaterThan(normal)
  })

  it('uses a separate short fault pattern for Gmail reconnect alerts', () => {
    playMailAlertSound({ eventId: 'mail-tone', urgent: true })
    const mailOscillators = started.length
    started.length = 0

    expect(playGmailReconnectAlertSound({ eventId: 'reconnect-tone' })).toBe(true)
    expect(started).toHaveLength(6)
    expect(started.length).not.toBe(mailOscillators)
    expect(playGmailReconnectAlertSound({ eventId: 'reconnect-tone' })).toBe(false)
  })
})
