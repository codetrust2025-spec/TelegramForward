/**
 * Global delivery: a notification sounds with no feature page mounted.
 *
 * This is the whole point of the manager. The tree rendered here contains no
 * Inbox, no recruitment page and no notifications page — only the manager — and
 * a tracked mail event still has to be audible. Before this existed, the same
 * event was silent unless the user happened to be on the right screen.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, cleanup } from '@testing-library/react'
import { installRecordingAudioStub } from './audioTestStub.js'

let mailHandler = null
const unsubscribe = vi.fn()

vi.mock('./mailEventStream.js', () => ({
  subscribeMailEvents: (handler) => {
    mailHandler = handler
    return unsubscribe
  },
  subscribeMailStatus: () => () => {},
  getMailStatus: () => 'Live',
}))

vi.mock('../context/AuthContext.jsx', () => ({
  useAuth: () => ({ authenticated: true, enabled: true, loading: false }),
}))

// The reminder poll has its own suite; keep its timer out of this one.
vi.mock('./useInterviewReminders.js', () => ({ useInterviewReminders: () => {} }))

const { GlobalNotificationSounds } = await import('./GlobalNotificationSounds.jsx')
const { __resetNotificationEvents } = await import('./notificationEvents.js')
const { stopUnreadGhost } = await import('./sounds/unreadGhost.js')

let audio

const SELECTION = {
  event: 'notification_created',
  classification: 'offer_received',
  event_id: 'evt-global-1',
}

beforeEach(() => {
  audio = installRecordingAudioStub()
  mailHandler = null
  __resetNotificationEvents()
  // The ambience is a module-level singleton: startUnreadGhost() returns early
  // while it is already running, creating no nodes. A test that inherited a
  // running loop from an earlier case would therefore see zero buffer sources
  // and fail on ordering rather than on behaviour.
  stopUnreadGhost()
  sessionStorage.clear()
  vi.stubGlobal(
    'fetch',
    vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ enabled: false }) })),
  )
  cleanup()
})

describe('sound without any feature page mounted', () => {
  it('subscribes to mail events on mount', () => {
    render(<GlobalNotificationSounds />)
    expect(mailHandler).toBeTypeOf('function')
  })

  it('plays a selection mail alert with no recruitment page in the tree', () => {
    render(<GlobalNotificationSounds />)
    audio.reset()
    mailHandler(SELECTION, { fromSocket: true })
    expect(audio.record.oscillators).toBeGreaterThan(0)
    expect([...new Set(audio.record.oscillatorTypes)]).toEqual(['sawtooth'])
  })

  it('does not sound for an event mirrored from another tab', () => {
    render(<GlobalNotificationSounds />)
    audio.reset()
    mailHandler(SELECTION, { fromSocket: false })
    expect(audio.record.oscillators).toBe(0)
  })

  it('does not replay a consumed event after a remount', () => {
    const first = render(<GlobalNotificationSounds />)
    mailHandler(SELECTION, { fromSocket: true })
    first.unmount()

    render(<GlobalNotificationSounds />)
    audio.reset()
    mailHandler(SELECTION, { fromSocket: true })
    expect(audio.record.oscillators).toBe(0)
  })

  it('releases its subscription on unmount', () => {
    const view = render(<GlobalNotificationSounds />)
    unsubscribe.mockClear()
    view.unmount()
    expect(unsubscribe).toHaveBeenCalled()
  })
})

describe('unread ambience is driven from props, not from the Inbox page', () => {
  it('starts above the threshold with no Inbox mounted', () => {
    audio.reset()
    render(<GlobalNotificationSounds inboxUnreadTotal={5} />)
    expect(audio.record.bufferSources).toBeGreaterThan(0)
    cleanup()
  })

  it('stays silent at the threshold', () => {
    audio.reset()
    render(<GlobalNotificationSounds inboxUnreadTotal={3} />)
    expect(audio.record.bufferSources).toBe(0)
  })
})
