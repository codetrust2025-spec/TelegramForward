import { accountLabel, postingModeForSlot, telegramDisplayName } from './accountUi.js'

/** Hours elapsed in the active stats window (IST calendar day, manual reset, or legacy 24h). */
export function statsWindowHours(statsWindow, resetTimestamp, cutoffTimestamp = 0) {
  const nowSec = Date.now() / 1000
  if (statsWindow === 'since_reset' && resetTimestamp > 0) {
    return Math.max(0.25, (nowSec - resetTimestamp) / 3600)
  }
  if (cutoffTimestamp > 0) {
    return Math.max(0.25, (nowSec - cutoffTimestamp) / 3600)
  }
  return 24
}

export function statsWindowLabel(statsWindow) {
  if (statsWindow === 'since_reset') return 'since reset'
  if (statsWindow === 'ist_day') return 'today IST'
  return '24h'
}

export function dailyStatsCutoff(dailyStats) {
  if (!dailyStats) return 0
  return Number(
    dailyStats.cutoff_timestamp
    ?? dailyStats.day_start_timestamp
    ?? dailyStats.reset_timestamp
    ?? 0,
  ) || 0
}

export function computePostsPerHour(forwards, statsWindow, resetTimestamp, cutoffTimestamp = 0) {
  const hours = statsWindowHours(statsWindow, resetTimestamp, cutoffTimestamp)
  return forwards / hours
}

function idleSendLabel(postingMode) {
  return postingMode === 'forwarding' ? 'No forwards yet' : 'No posts yet'
}

/**
 * @returns {'ok'|'warn'|'critical'|null}
 */
export function fleetAttentionLevel(row, loggedIn, postingMode = 'campaign') {
  const health = row.health ?? 100
  const reasons = []

  if (health < 50) reasons.push('low_health')
  else if (health < 80) reasons.push('health')

  if (loggedIn && !row.running) reasons.push('stopped')
  if (loggedIn && row.running && (row.messagesSent24h ?? 0) === 0) {
    reasons.push(postingMode === 'forwarding' ? 'no_forwards' : 'no_posts')
  }
  if (row.status === 'rate_limited' || row.status === 'flood_wait') reasons.push('limited')

  if (reasons.includes('low_health') || reasons.includes('stopped')) return 'critical'
  if (reasons.length > 0) return 'warn'
  return null
}

export function fleetAttentionLabel(level, row, loggedIn, postingMode = 'campaign') {
  if (!level) return null
  const parts = []
  const health = row.health ?? 100
  if (health < 50) parts.push('Low health')
  else if (health < 80) parts.push('Health recovering')
  if (loggedIn && !row.running) parts.push('Worker stopped')
  if (loggedIn && row.running && (row.messagesSent24h ?? 0) === 0) {
    parts.push(idleSendLabel(postingMode))
  }
  if (row.status === 'rate_limited' || row.status === 'flood_wait') parts.push('Rate limited')
  return parts.join(' · ') || 'Needs attention'
}

export function buildFleetHealthRows(
  perAccount,
  accountInfo,
  statsWindow,
  resetTimestamp,
  options = {},
) {
  const { postingModes = {}, accountStates = {}, cutoffTimestamp = 0 } = options
  const hours = statsWindowHours(statsWindow, resetTimestamp, cutoffTimestamp)
  const windowLabel = statsWindowLabel(statsWindow)

  return perAccount.map((row) => {
    const info = accountInfo?.[row.slot]
    const loggedIn = !!info
    const postingMode = postingModeForSlot(accountStates, row.slot, postingModes)
    const forwards = row.messagesSent24h ?? 0
    const rate = computePostsPerHour(forwards, statsWindow, resetTimestamp, cutoffTimestamp)
    const attention = fleetAttentionLevel(row, loggedIn, postingMode)
    return {
      ...row,
      loggedIn,
      postingMode,
      displayName: telegramDisplayName(info) || '—',
      shortLabel: accountLabel(row.slot).replace('Account ', 'A'),
      forwards,
      postsPerHour: rate,
      windowLabel,
      windowHours: hours,
      attention,
      attentionHint: fleetAttentionLabel(attention, row, loggedIn, postingMode),
    }
  })
}

export function sortFleetHealthRows(rows) {
  const order = { critical: 0, warn: 1, ok: 2 }
  return [...rows].sort((a, b) => {
    const ao = a.attention ? order[a.attention] ?? 1 : 2
    const bo = b.attention ? order[b.attention] ?? 1 : 2
    if (ao !== bo) return ao - bo
    return (a.postsPerHour ?? 0) - (b.postsPerHour ?? 0)
  })
}

export function formatPostsPerHour(rate) {
  if (!Number.isFinite(rate) || rate <= 0) return '0'
  if (rate >= 10) return rate.toFixed(1)
  return rate.toFixed(2)
}
