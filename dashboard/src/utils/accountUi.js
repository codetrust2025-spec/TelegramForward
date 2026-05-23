/** Shared account / status helpers for dashboard UI */

export const RUN_UI = {
  text: '#22c55e',
  border: '#166534',
  borderActive: '#22c55e',
  bg: '#14251a',
  bgActive: '#1a2e22',
  badge: '#16a34a',
}

export const SLEEP_UI = {
  text: '#fbbf24',
  border: '#713f12',
  borderActive: '#b45309',
  bg: '#1a1814',
  bgActive: '#1f1a14',
  badge: '#b45309',
}

export function formatDurationShort(seconds) {
  const s = Math.max(0, Number(seconds) || 0)
  if (s >= 86400) return `${Math.floor(s / 86400)}d ${Math.floor((s % 86400) / 3600)}h`
  if (s >= 3600) return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`
  if (s >= 60) return `${Math.floor(s / 60)}m ${s % 60}s`
  return `${s}s`
}

export function isHeavyRateLimit(acctState) {
  return !!(acctState?.heavy_rate_limit || (
    acctState?.status === 'flood_wait' &&
    (acctState?.notification || '').toLowerCase().includes('heavy rate limit')
  ))
}

export function sleepSummary(acctState) {
  if (!isHeavyRateLimit(acctState)) return null
  const left = acctState?.next_cycle_in > 0 ? formatDurationShort(acctState.next_cycle_in) : null
  return left ? `Sleeping · ~${left} left` : 'Sleeping (rate limited)'
}

export function accountLabel(slot) {
  const m = String(slot).match(/^account(\d+)$/i)
  return m ? `Account ${m[1]}` : slot
}

/** Telegram display name (first + last), or @username, or phone. */
export function telegramDisplayName(info) {
  if (!info) return null
  const name = String(info.name || '').trim()
  const first = String(info.first_name || '').trim()
  const last = String(info.last_name || '').trim()
  const full = name || [first, last].filter(Boolean).join(' ')
  const user = String(info.username || '').trim().replace(/^@/, '')
  if (full) return full
  if (user) return `@${user}`
  const phone = String(info.phone || '').trim()
  if (phone) return phone.startsWith('+') ? phone : `+${phone}`
  return null
}

/** @username line for mini cards (null if no username). */
export function telegramUsername(info) {
  if (!info) return null
  const user = String(info.username || '').trim().replace(/^@/, '')
  return user ? `@${user}` : null
}

/** Tooltip / title for an account card. */
export function accountCardTitle(slot, info) {
  const label = accountLabel(slot)
  const tg = telegramDisplayName(info)
  const user = telegramUsername(info)
  if (!tg) return label
  if (user && tg !== user && !tg.includes(user)) {
    return `${label} — ${tg} (${user})`
  }
  return `${label} — ${tg}`
}

export function formatJoinedStats(info) {
  if (!info || info.joined_total == null || info.joined_total === undefined) return null
  const total = Number(info.joined_total) || 0
  const groups = Number(info.joined_groups) || 0
  const channels = Number(info.joined_channels) || 0
  return { total, groups, channels, updated: info.joined_updated_at || '' }
}

/** @deprecated alias — same as formatJoinedStats */
export const formatTelegramMembership = formatJoinedStats

export const TELEGRAM_MEMBERSHIP_TOOLTIP =
  'How many chats this account belongs to on Telegram (from a dialog scan). This is your real Telegram membership—not the upload list the bot posts to.'

export const JOINS_TODAY_TOOLTIP =
  'New groups this bot joined today via automation. Resets at UTC midnight and is rate-limited separately from Telegram membership.'

/** Cycle stat tiles on the account detail card. */
export const CYCLE_METRIC_SENT_TOOLTIP =
  'Messages posted successfully in the current cycle (resets when a new cycle starts).'

export const CYCLE_METRIC_FAILED_TOOLTIP =
  'Groups where posting failed in the current cycle (rate limits, blocks, errors).'

export const CYCLE_METRIC_SKIPPED_TOOLTIP =
  'Skipped this cycle because your message is already visible in recent chat history.'

export const CYCLE_METRIC_LIST_TOOLTIP =
  'Groups from your uploaded master list assigned to this account for posting. The bot cycles through these targets—not the same as “On Telegram” membership below.'

function formatScannedAt(iso) {
  if (!iso) return null
  try {
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return null
    return d.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return null
  }
}

export { formatScannedAt as formatMembershipScannedAt }

export function formatTelegramMembershipTooltip(membership) {
  if (!membership) return TELEGRAM_MEMBERSHIP_TOOLTIP
  const parts = [`${membership.groups} groups`, `${membership.channels} channels`]
  const scanned = formatScannedAt(membership.updated)
  if (scanned) parts.push(`scanned ${scanned}`)
  return `${TELEGRAM_MEMBERSHIP_TOOLTIP}\n\n${parts.join(' · ')}`
}

export function formatJoinStatsToday(acctState) {
  const js = acctState?.join_stats
  if (!js) return null
  const today = Number(js.joins_today) || 0
  const limit = js.joins_daily_limit != null ? Number(js.joins_daily_limit) : null
  return {
    today,
    limit: limit != null && !Number.isNaN(limit) ? limit : null,
    restricted: !!js.restriction_active,
  }
}

const MEMBERSHIP_STALE_MS = 10 * 60 * 1000

function parseMembershipUpdatedAt(raw) {
  if (!raw) return null
  const text = String(raw).trim()
  if (text.endsWith(' UTC')) {
    const iso = text.replace(' UTC', ':00Z').replace(' ', 'T')
    const d = new Date(iso)
    return Number.isNaN(d.getTime()) ? null : d
  }
  const d = new Date(text)
  return Number.isNaN(d.getTime()) ? null : d
}

/** True when On Telegram scan is older than 10 minutes (or never run). */
export function isMembershipStale(info, thresholdMs = MEMBERSHIP_STALE_MS) {
  if (!info?.phone) return false
  if (info.joined_total == null || info.joined_total === undefined) return true
  if (info.membership_stale === true) return true
  const updated = parseMembershipUpdatedAt(info.joined_updated_at)
  if (!updated) return true
  return Date.now() - updated.getTime() > thresholdMs
}

export function formatMembershipAge(info) {
  const updated = parseMembershipUpdatedAt(info?.joined_updated_at)
  if (!updated) return null
  const mins = Math.floor((Date.now() - updated.getTime()) / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 48) return `${hrs}h ago`
  return updated.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

/** Matches backend classify_account_info — manual list + Telegram Premium only. */
export function detectSubscriptionFromInfo(info) {
  if (!info || !info.phone) return false
  if (info.is_subscription === true) return true
  if (info.telegram_premium === true) return true
  return false
}

/** Manual list + API list + per-account info flags. */
export function isSubscriptionAccount(slot, subscriptionSlots, accountInfo) {
  if (!slot) return false
  if (Array.isArray(subscriptionSlots) && subscriptionSlots.includes(slot)) return true
  const info = accountInfo?.[slot] ?? accountInfo
  return detectSubscriptionFromInfo(info)
}

export function filterAccountsByRole(slots, subscriptionSlots, accountInfo, role) {
  if (role === 'all') return slots
  if (role === 'subscription') {
    return slots.filter(s => isSubscriptionAccount(s, subscriptionSlots, accountInfo))
  }
  if (role === 'posting') {
    return slots.filter(s => !isSubscriptionAccount(s, subscriptionSlots, accountInfo))
  }
  return slots
}

export function sortAccountSlots(slots) {
  return [...slots].sort((a, b) => {
    const na = parseInt(String(a).replace(/\D/g, ''), 10) || 0
    const nb = parseInt(String(b).replace(/\D/g, ''), 10) || 0
    return na - nb
  })
}

export function isAccountLoggedIn(accountInfo, slot) {
  const info = accountInfo?.[slot]
  return !!(info && (info.phone || info.user_id))
}

/** Slots with a saved Telegram session (shown in the account grid). */
export function getLoggedInSlots(slots, accountInfo) {
  return sortAccountSlots(slots.filter(s => isAccountLoggedIn(accountInfo, s)))
}

/** First configured slot with no login — for “Add account”. */
export function getNextAvailableSlot(slots, accountInfo) {
  return sortAccountSlots(slots).find(s => !isAccountLoggedIn(accountInfo, s)) ?? null
}

export function getAccountSlots(state, configuredSlots) {
  const fromApi = Array.isArray(state?.account_slots) ? state.account_slots : []
  const extra = Array.isArray(configuredSlots) ? configuredSlots : []
  const merged = [...new Set([...fromApi, ...extra])]
  return sortAccountSlots(merged)
}

export function sortAccountsForDisplay(slots, accountStates, accountInfo) {
  const rank = (slot) => {
    const acct = accountStates?.[slot]
    if (isHeavyRateLimit(acct)) return 3
    if (acct?.running) return 0
    if (accountInfo?.[slot]) return 1
    return 2
  }
  const slotNum = (slot) => parseInt(String(slot).replace(/\D/g, ''), 10) || 0
  return [...slots].sort((a, b) => {
    const d = rank(a) - rank(b)
    return d !== 0 ? d : slotNum(a) - slotNum(b)
  })
}

/** running | sleeping | rate_limited | stopped | idle */
export function getAccountStatus(acctState, loggedIn, accountStatus) {
  if (!loggedIn) return 'idle'
  const lifecycle = accountStatus?.lifecycle
  if (lifecycle === 'ERROR') return 'rate_limited'
  if (lifecycle === 'SLEEPING' || isHeavyRateLimit(acctState)) return 'sleeping'
  if (!acctState) return lifecycle === 'RUNNING' ? 'running' : 'stopped'
  if (acctState.status === 'flood_wait') return 'rate_limited'
  if (lifecycle === 'RUNNING' || acctState.running) return 'running'
  return 'stopped'
}

const STATUS_LABELS = {
  running: 'Running',
  sleeping: 'Sleeping',
  rate_limited: 'Rate limited',
  stopped: 'Stopped',
  idle: 'Not logged in',
}

export function formatAccountStatusLabel(status) {
  return STATUS_LABELS[status] || 'Unknown'
}

/** Compact lines for sidebar mini cards. */
export function formatJoinedStatsLine(info, acctState) {
  const membership = formatJoinedStats(info)
  if (!membership) return null
  const parts = [
    `${membership.total} on Telegram`,
    `${membership.groups} groups · ${membership.channels} channels`,
  ]
  const scanned = formatScannedAt(membership.updated)
  if (scanned) parts.push(`scanned ${scanned}`)
  const joinToday = formatJoinStatsToday(acctState)
  if (joinToday) {
    const cap = joinToday.limit != null ? `/${joinToday.limit}` : ''
    parts.push(`${joinToday.today}${cap} joins today`)
  }
  return parts
}

export function formatQueueStatus(accountStatus) {
  if (!accountStatus) return null
  const depth = accountStatus.queue_depth ?? 0
  const max = accountStatus.queue_max_size
  if (depth <= 0 && !accountStatus.queue_processing && !accountStatus.queue_high_watermark) return null
  const proc = accountStatus.queue_processing ? ' · sending' : ''
  const cap = max ? `/${max}` : ''
  const warn = accountStatus.queue_high_watermark ? ' ⚠' : ''
  return `Queue: ${depth}${cap}${proc}${warn}`
}

export function formatPhoneDisplay(phone) {
  if (!phone) return ''
  const p = String(phone).trim()
  return p.startsWith('+') ? p : `+${p}`
}

/** good | warning | bad | unknown */
export function getHealthLevel(acctState) {
  if (!acctState) return 'unknown'
  const h = acctState.health_score
  if (h != null && !Number.isNaN(Number(h))) {
    const n = Number(h)
    if (n <= 0) return 'unknown'
    if (n >= 70) return 'good'
    if (n >= 40) return 'warning'
    return 'bad'
  }
  if (isHeavyRateLimit(acctState)) return 'bad'
  if (acctState.running && (acctState.flood_streak || 0) > 2) return 'warning'
  if (acctState.running) return 'good'
  return 'unknown'
}

export function formatLogTime(time) {
  if (!time) return '--:--:--'
  if (typeof time === 'string' && /^\d{2}:\d{2}:\d{2}$/.test(time)) return time
  try {
    const d = new Date(time)
    if (!Number.isNaN(d.getTime())) {
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
    }
  } catch { /* ignore */ }
  return String(time)
}

export function formatCountdown(seconds) {
  const s = Math.max(0, Number(seconds) || 0)
  if (s >= 60) return `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, '0')}s`
  return `${s}s`
}

/** Backend profile labels for tuned accounts (account7/8). */
export function accountProfileHint(slot) {
  const hints = {
    account7: 'Balanced',
    account8: 'Safe',
  }
  return hints[slot] || null
}
