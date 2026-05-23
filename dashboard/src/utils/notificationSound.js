/** Incoming DM notification chime (Web Audio). Requires one user click to unlock autoplay. */

import { isMessageSoundMuted } from './soundQuietHours.js'

let audioCtx = null
let unlocked = false

const recentKeys = new Map()
const DEDUPE_MS = 4000

function getContext() {
  const Ctx = window.AudioContext || window.webkitAudioContext
  if (!Ctx) return null
  if (!audioCtx) audioCtx = new Ctx()
  return audioCtx
}

/** Play a near-silent blip — browsers require audio during the gesture that unlocks. */
function playSilentUnlockBlip(ctx) {
  try {
    const t0 = ctx.currentTime
    const osc = ctx.createOscillator()
    const g = ctx.createGain()
    g.gain.setValueAtTime(0.001, t0)
    osc.connect(g)
    g.connect(ctx.destination)
    osc.start(t0)
    osc.stop(t0 + 0.02)
  } catch {
    /* ignore */
  }
}

/**
 * Call on user interaction (click/key) so later notification sounds are allowed.
 * Safe to call repeatedly.
 */
export function unlockNotificationSound() {
  const ctx = getContext()
  if (!ctx) return

  const finish = () => {
    playSilentUnlockBlip(ctx)
    unlocked = true
  }

  if (ctx.state === 'suspended') {
    ctx.resume().then(finish).catch(() => {})
  } else {
    finish()
  }
}

function shouldPlay(slot, messageId) {
  if (messageId == null) return true
  const key = `${slot}:${messageId}`
  const now = Date.now()
  const last = recentKeys.get(key)
  if (last != null && now - last < DEDUPE_MS) return false
  recentKeys.set(key, now)
  for (const [k, t] of recentKeys) {
    if (now - t > DEDUPE_MS * 2) recentKeys.delete(k)
  }
  return true
}

function runChime(ctx) {
  const t0 = ctx.currentTime
  const master = ctx.createGain()
  master.gain.setValueAtTime(0.45, t0)
  master.gain.exponentialRampToValueAtTime(0.001, t0 + 0.4)
  master.connect(ctx.destination)

  const playTone = (freq, start, duration) => {
    const osc = ctx.createOscillator()
    const g = ctx.createGain()
    osc.type = 'sine'
    osc.frequency.setValueAtTime(freq, t0 + start)
    g.gain.setValueAtTime(0.001, t0 + start)
    g.gain.exponentialRampToValueAtTime(0.95, t0 + start + 0.02)
    g.gain.exponentialRampToValueAtTime(0.001, t0 + start + duration)
    osc.connect(g)
    g.connect(master)
    osc.start(t0 + start)
    osc.stop(t0 + start + duration + 0.03)
  }

  playTone(880, 0, 0.12)
  playTone(1174.66, 0.1, 0.2)
}

/**
 * Play notification for a new incoming DM.
 * @param {{ slot?: string, messageId?: number|string }} opts
 */
export function playNewMessageSound(opts = {}) {
  if (isMessageSoundMuted()) return
  const { slot = '', messageId } = opts
  if (!shouldPlay(slot, messageId)) return

  const ctx = getContext()
  if (!ctx) return

  const play = () => {
    try {
      runChime(ctx)
    } catch {
      /* ignore */
    }
  }

  if (ctx.state === 'suspended') {
    ctx.resume().then(play).catch(() => {})
  } else {
    play()
  }
}

export function isNotificationSoundUnlocked() {
  return unlocked
}

export function getSharedAudioContext() {
  return getContext()
}

/* ── Continuous ghost alert when unread count > 3 ────────────────────── */

const UNREAD_MUSIC_THRESHOLD = 3

let alertMusicActive = false
let alertMusicTimer = null
let alertMusicMaster = null
let alertRunningNodes = []

function trackNode(node) {
  alertRunningNodes.push(node)
  return node
}

function stopInboxAlertMusic() {
  alertMusicActive = false
  if (alertMusicTimer != null) {
    clearTimeout(alertMusicTimer)
    alertMusicTimer = null
  }
  const now = alertMusicMaster?.context?.currentTime ?? 0
  for (const node of alertRunningNodes) {
    try {
      if (node.stop) node.stop(now + 0.02)
    } catch {
      /* already stopped */
    }
    try {
      node.disconnect()
    } catch {
      /* ignore */
    }
  }
  alertRunningNodes = []
  if (alertMusicMaster) {
    try {
      alertMusicMaster.gain.exponentialRampToValueAtTime(0.001, now + 0.25)
      const m = alertMusicMaster
      setTimeout(() => {
        try {
          m.disconnect()
        } catch {
          /* ignore */
        }
      }, 300)
    } catch {
      /* ignore */
    }
    alertMusicMaster = null
  }
}

/** Looping haunted wind (brown noise + swaying low-pass). */
function startGhostWind(ctx, dest) {
  const t = ctx.currentTime
  const len = Math.floor(ctx.sampleRate * 4)
  const buffer = ctx.createBuffer(1, len, ctx.sampleRate)
  const data = buffer.getChannelData(0)
  let brown = 0
  for (let i = 0; i < len; i += 1) {
    brown = brown * 0.985 + (Math.random() * 2 - 1) * 0.08
    data[i] = brown
  }
  const src = trackNode(ctx.createBufferSource())
  src.buffer = buffer
  src.loop = true
  const filter = trackNode(ctx.createBiquadFilter())
  filter.type = 'lowpass'
  filter.frequency.setValueAtTime(320, t)
  filter.Q.setValueAtTime(1.2, t)
  const windGain = trackNode(ctx.createGain())
  windGain.gain.setValueAtTime(0.14, t)
  const lfo = trackNode(ctx.createOscillator())
  lfo.type = 'sine'
  lfo.frequency.setValueAtTime(0.12 + Math.random() * 0.08, t)
  const lfoAmp = trackNode(ctx.createGain())
  lfoAmp.gain.setValueAtTime(280, t)
  lfo.connect(lfoAmp)
  lfoAmp.connect(filter.frequency)
  src.connect(filter)
  filter.connect(windGain)
  windGain.connect(dest)
  src.start(t)
  lfo.start(t)
}

/** Low spirit moan — pitch sinks like a ghost passing by. */
function playGhostMoan(ctx, dest, start) {
  const dur = 2.2 + Math.random() * 1.4
  const osc = trackNode(ctx.createOscillator())
  osc.type = 'sine'
  const f0 = 220 + Math.random() * 140
  osc.frequency.setValueAtTime(f0, start)
  osc.frequency.exponentialRampToValueAtTime(Math.max(55, f0 * 0.28), start + dur)
  const osc2 = trackNode(ctx.createOscillator())
  osc2.type = 'triangle'
  osc2.frequency.setValueAtTime(f0 * 1.015, start)
  osc2.frequency.exponentialRampToValueAtTime(Math.max(60, f0 * 0.3), start + dur)
  const filter = trackNode(ctx.createBiquadFilter())
  filter.type = 'bandpass'
  filter.frequency.setValueAtTime(450, start)
  filter.Q.setValueAtTime(6, start)
  const g = trackNode(ctx.createGain())
  g.gain.setValueAtTime(0.001, start)
  g.gain.linearRampToValueAtTime(0.26, start + 0.55)
  g.gain.linearRampToValueAtTime(0.18, start + dur * 0.65)
  g.gain.exponentialRampToValueAtTime(0.001, start + dur)
  osc.connect(filter)
  osc2.connect(filter)
  filter.connect(g)
  g.connect(dest)
  osc.start(start)
  osc2.start(start)
  osc.stop(start + dur + 0.05)
  osc2.stop(start + dur + 0.05)
}

/** Ethereal whisper — airy noise through a high filter. */
function playGhostWhisper(ctx, dest, start) {
  const len = Math.floor(ctx.sampleRate * (0.5 + Math.random() * 0.5))
  const buffer = ctx.createBuffer(1, len, ctx.sampleRate)
  const data = buffer.getChannelData(0)
  for (let i = 0; i < len; i += 1) {
    data[i] = (Math.random() * 2 - 1) * Math.sin((Math.PI * i) / len)
  }
  const src = trackNode(ctx.createBufferSource())
  src.buffer = buffer
  const filter = trackNode(ctx.createBiquadFilter())
  filter.type = 'bandpass'
  filter.frequency.setValueAtTime(1400 + Math.random() * 900, start)
  filter.Q.setValueAtTime(4, start)
  const g = trackNode(ctx.createGain())
  g.gain.setValueAtTime(0.001, start)
  g.gain.linearRampToValueAtTime(0.1, start + 0.15)
  g.gain.exponentialRampToValueAtTime(0.001, start + len / ctx.sampleRate)
  src.connect(filter)
  filter.connect(g)
  g.connect(dest)
  src.start(start)
  src.stop(start + len / ctx.sampleRate + 0.02)
}

/** Distant spirit wail — thin detuned tones with slow tremolo. */
function playSpiritWail(ctx, dest, start) {
  const dur = 1.6 + Math.random() * 0.8
  const base = 520 + Math.random() * 280
  for (const det of [0, 7, -5]) {
    const osc = trackNode(ctx.createOscillator())
    osc.type = 'sine'
    osc.frequency.setValueAtTime(base + det, start)
    const trem = trackNode(ctx.createOscillator())
    trem.frequency.setValueAtTime(5 + Math.random() * 3, start)
    const tremG = trackNode(ctx.createGain())
    tremG.gain.setValueAtTime(12, start)
    trem.connect(tremG)
    tremG.connect(osc.detune)
    const g = trackNode(ctx.createGain())
    g.gain.setValueAtTime(0.001, start)
    g.gain.linearRampToValueAtTime(0.08, start + 0.25)
    g.gain.exponentialRampToValueAtTime(0.001, start + dur)
    osc.connect(g)
    g.connect(dest)
    osc.start(start)
    trem.start(start)
    osc.stop(start + dur + 0.05)
    trem.stop(start + dur + 0.05)
  }
}

/** Rare hollow knock / creak from the void. */
function playVoidCreak(ctx, dest, start) {
  const osc = trackNode(ctx.createOscillator())
  osc.type = 'triangle'
  osc.frequency.setValueAtTime(180, start)
  osc.frequency.exponentialRampToValueAtTime(45, start + 0.35)
  const g = trackNode(ctx.createGain())
  g.gain.setValueAtTime(0.16, start)
  g.gain.exponentialRampToValueAtTime(0.001, start + 0.4)
  osc.connect(g)
  g.connect(dest)
  osc.start(start)
  osc.stop(start + 0.45)
}

function scheduleGhostAmbience(ctx) {
  if (!alertMusicActive || !alertMusicMaster) return

  const now = ctx.currentTime
  const roll = Math.random()

  if (roll < 0.38) {
    playGhostMoan(ctx, alertMusicMaster, now)
  } else if (roll < 0.62) {
    playGhostWhisper(ctx, alertMusicMaster, now)
  } else if (roll < 0.82) {
    playSpiritWail(ctx, alertMusicMaster, now)
  } else {
    playVoidCreak(ctx, alertMusicMaster, now)
  }

  const delay = 480 + Math.random() * 900
  alertMusicTimer = window.setTimeout(() => scheduleGhostAmbience(ctx), delay)
}

function startInboxAlertMusic() {
  if (alertMusicActive) return
  const ctx = getContext()
  if (!ctx) return

  const begin = () => {
    stopInboxAlertMusic()
    alertMusicActive = true
    alertMusicMaster = trackNode(ctx.createGain())
    alertMusicMaster.gain.setValueAtTime(0.42, ctx.currentTime)
    alertMusicMaster.connect(ctx.destination)
    startGhostWind(ctx, alertMusicMaster)
    scheduleGhostAmbience(ctx)
  }

  if (ctx.state === 'suspended') {
    ctx.resume().then(begin).catch(() => {})
  } else {
    begin()
  }
}

/**
 * Start/stop looping alert music based on total unread inbox count.
 * Plays continuously while count > 3; stops at 3 or below.
 */
export function syncInboxAlertMusic(unreadCount) {
  if (isMessageSoundMuted()) {
    stopInboxAlertMusic()
    return
  }
  const n = Math.max(0, Number(unreadCount) || 0)
  if (n > UNREAD_MUSIC_THRESHOLD) {
    startInboxAlertMusic()
  } else {
    stopInboxAlertMusic()
  }
}

export function stopInboxAlertMusicOnUnmount() {
  stopInboxAlertMusic()
}

/* ── Incoming voice call ring (repeating) ───────────────────────────── */

let callRingTimer = null
let callRingNodes = []

function stopCallRingNodes() {
  if (callRingTimer != null) {
    clearInterval(callRingTimer)
    callRingTimer = null
  }
  const now = callRingNodes[0]?.context?.currentTime ?? 0
  for (const node of callRingNodes) {
    try {
      if (node.stop) node.stop(now + 0.02)
    } catch {
      /* ignore */
    }
    try {
      node.disconnect()
    } catch {
      /* ignore */
    }
  }
  callRingNodes = []
}

/** Classic two-tone ring pattern (≈1.2s). */
function playCallRingBurst(ctx) {
  const t0 = ctx.currentTime
  const master = ctx.createGain()
  master.gain.setValueAtTime(0.55, t0)
  master.gain.exponentialRampToValueAtTime(0.001, t0 + 1.25)
  master.connect(ctx.destination)
  callRingNodes.push(master)

  const tone = (freq, start, dur) => {
    const osc = ctx.createOscillator()
    const g = ctx.createGain()
    osc.type = 'sine'
    osc.frequency.setValueAtTime(freq, t0 + start)
    g.gain.setValueAtTime(0.001, t0 + start)
    g.gain.exponentialRampToValueAtTime(0.9, t0 + start + 0.03)
    g.gain.exponentialRampToValueAtTime(0.001, t0 + start + dur)
    osc.connect(g)
    g.connect(master)
    osc.start(t0 + start)
    osc.stop(t0 + start + dur + 0.02)
    callRingNodes.push(osc, g)
  }

  tone(440, 0, 0.4)
  tone(480, 0.45, 0.4)
  tone(440, 0.9, 0.35)
}

/**
 * Looping ringtone for incoming Telegram voice calls or call reminders.
 */
export function startIncomingCallRing() {
  if (isMessageSoundMuted()) return
  const ctx = getContext()
  if (!ctx) return

  const begin = () => {
    stopCallRingNodes()
    playCallRingBurst(ctx)
    callRingTimer = window.setInterval(() => {
      if (!callRingTimer) return
      playCallRingBurst(ctx)
    }, 2800)
  }

  if (ctx.state === 'suspended') {
    ctx.resume().then(begin).catch(() => {})
  } else {
    begin()
  }
}

export function stopIncomingCallRing() {
  stopCallRingNodes()
}
