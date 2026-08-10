/**
 * The ten notification sounds must stay ten *different* sounds.
 *
 * The regression this guards against is real and recent: the 10- and 20-minute
 * reply alerts were one function with an `aggressive` flag, and the interview
 * booking and selection mails were one klaxon with a different sweep count. In
 * both cases the product had two notifications and one sound identity.
 */

import { beforeEach, describe, expect, it } from 'vitest'
import { NOTIFICATION_IDS, NOTIFICATION_SOUNDS } from './soundRegistry.js'
import { installRecordingAudioStub } from './audioTestStub.js'

describe('notification sound catalogue', () => {
  it('covers exactly the eleven audible notifications', () => {
    expect(NOTIFICATION_IDS).toHaveLength(11)
    expect(Object.keys(NOTIFICATION_SOUNDS).sort()).toEqual([...NOTIFICATION_IDS].sort())
  })

  it('gives every notification its own play function', () => {
    const fns = NOTIFICATION_IDS.map((id) => NOTIFICATION_SOUNDS[id].play)
    expect(new Set(fns).size).toBe(NOTIFICATION_IDS.length)
  })

  it('never points two notifications at the same module export', () => {
    const byFunction = new Map()
    for (const id of NOTIFICATION_IDS) {
      const fn = NOTIFICATION_SOUNDS[id].play
      const clash = byFunction.get(fn)
      expect(clash, `${id} reuses the sound of ${clash}`).toBeUndefined()
      byFunction.set(fn, id)
    }
  })

  it('describes a dedupe rule for every notification', () => {
    for (const id of NOTIFICATION_IDS) {
      expect(NOTIFICATION_SOUNDS[id].dedupe, id).toBeTruthy()
    }
  })

  it('only marks looping sounds as loops, and gives each a stop', () => {
    for (const id of NOTIFICATION_IDS) {
      const entry = NOTIFICATION_SOUNDS[id]
      if (entry.loop) expect(entry.stop, id).toBeTypeOf('function')
      else expect(entry.stop, id).toBeNull()
    }
    const looping = NOTIFICATION_IDS.filter((id) => NOTIFICATION_SOUNDS[id].loop)
    expect(looping.sort()).toEqual([
      'call_reminder',
      'incoming_call',
      'sla_10',
      'sla_20',
      'unread_ghost',
    ])
  })
})

describe('every sound renders a different signature', () => {
  let audio

  beforeEach(() => {
    audio = installRecordingAudioStub()
  })

  /** Ids whose sound is a continuous loop are sampled by starting them once. */
  const ONE_SHOT = NOTIFICATION_IDS.filter((id) => id !== 'unread_ghost')

  it('produces a distinct waveform/pitch fingerprint per notification', () => {
    const signatures = new Map()

    for (const id of ONE_SHOT) {
      audio.reset()
      NOTIFICATION_SOUNDS[id].play()
      const signature = audio.signature()
      const clash = signatures.get(signature)
      expect(clash, `${id} sounds identical to ${clash}`).toBeUndefined()
      signatures.set(signature, id)
      if (NOTIFICATION_SOUNDS[id].stop) NOTIFICATION_SOUNDS[id].stop()
    }

    expect(signatures.size).toBe(ONE_SHOT.length)
  })

  it('separates the 10-minute pulse from the 20-minute siren', () => {
    audio.reset()
    NOTIFICATION_SOUNDS.sla_10.play()
    const pulse = audio.record
    const pulseWaveforms = [...new Set(pulse.oscillatorTypes)]
    const pulseOscillators = pulse.oscillators

    audio.reset()
    NOTIFICATION_SOUNDS.sla_20.play()
    const sirenWaveforms = [...new Set(audio.record.oscillatorTypes)]

    // Square blips versus a sawtooth glide: different waveform, and the siren
    // is one long voice where the pulse is two short ones.
    expect(pulseWaveforms).toEqual(['square'])
    expect(sirenWaveforms).toEqual(['sawtooth'])
    expect(pulseOscillators).toBeGreaterThan(audio.record.oscillators)
    NOTIFICATION_SOUNDS.sla_20.stop()
  })

  it('separates the interview booking bell from the selection fanfare', () => {
    audio.reset()
    NOTIFICATION_SOUNDS.mail_interview_booking.play()
    const bellWaveforms = [...new Set(audio.record.oscillatorTypes)]
    const bellPitches = [...new Set(audio.record.frequencies)]

    audio.reset()
    NOTIFICATION_SOUNDS.mail_selection.play()
    const fanfareWaveforms = [...new Set(audio.record.oscillatorTypes)]
    const fanfarePitches = [...new Set(audio.record.frequencies)]

    expect(bellWaveforms).toEqual(['sine'])
    expect(fanfareWaveforms).toEqual(['sawtooth'])
    expect(bellPitches).not.toEqual(fanfarePitches)
  })

  it('separates the scheduled call reminder from the incoming call ring', () => {
    audio.reset()
    NOTIFICATION_SOUNDS.incoming_call.play()
    const ringWaveforms = [...new Set(audio.record.oscillatorTypes)]
    const ringPitches = [...new Set(audio.record.frequencies)]
    NOTIFICATION_SOUNDS.incoming_call.stop()

    audio.reset()
    NOTIFICATION_SOUNDS.call_reminder.play()
    const reminderWaveforms = [...new Set(audio.record.oscillatorTypes)]
    const reminderPitches = [...new Set(audio.record.frequencies)]
    NOTIFICATION_SOUNDS.call_reminder.stop()

    // Sine tones held together versus a gliding triangle figure. The reminder
    // used to *be* the ring, so this is the regression that matters most here.
    expect(ringWaveforms).toEqual(['sine'])
    expect(reminderWaveforms).toEqual(['triangle'])
    expect(reminderPitches).not.toEqual(ringPitches)
  })

  it('builds the ghost ambience from noise, unlike every event sound', () => {
    audio.reset()
    NOTIFICATION_SOUNDS.unread_ghost.start()
    expect(audio.record.bufferSources).toBeGreaterThan(0)
    NOTIFICATION_SOUNDS.unread_ghost.stop()
  })
})
