import {
  getAccountStatus,
  isCampaignEnabled,
  isForwardingEnabled,
  isHeavyRateLimit,
} from './accountUi'

function featureMetrics(acct, modeFilter) {
  if (!acct) {
    return {
      success: 0,
      failed: 0,
      skippedAlreadyPosted: 0,
      skippedCooldown: 0,
      skippedOther: 0,
      active: 0,
      cycle: 0,
      tickMax: 0,
      sentSinceReset: 0,
      currentGroup: '',
    }
  }

  if (modeFilter === 'forwarding') {
    const fwd = acct.forwarding || {}
    const success = Number(fwd.success ?? acct.forwarding_success ?? 0)
    const failed = Number(fwd.failed ?? acct.forwarding_failed ?? 0)
    const skippedAlreadyPosted = Number(
      fwd.skipped_already_posted ?? acct.forwarding_skipped_already_posted ?? 0,
    )
    const active = Number(fwd.active_groups ?? acct.forwarding_active_groups ?? 0)
    const cycle = Number(fwd.cycle ?? acct.forwarding_cycle ?? 0)
    const tickProcessed = success + failed + skippedAlreadyPosted
    const tickTotal = active || Number(acct.forward_batch_size ?? fwd.forward_batch_size ?? 0) || 100
    const tickRemaining = Math.max(0, tickTotal - tickProcessed)
    return {
      success,
      failed,
      skippedAlreadyPosted,
      skippedCooldown: 0,
      skippedOther: 0,
      active,
      cycle,
      tickTotal,
      tickRemaining,
      tickProcessed,
      tickMax: tickTotal,
      sentSinceReset: Number(acct.forward_posts_24h ?? 0),
      currentGroup: fwd.current_group ?? acct.forwarding_current_group ?? acct.current_group ?? '',
    }
  }

  if (modeFilter === 'campaign') {
    const camp = acct.campaign || {}
    const success = Number(camp.success ?? acct.campaign_success ?? 0)
    const failed = Number(camp.failed ?? acct.campaign_failed ?? 0)
    const skippedAlreadyPosted = Number(
      camp.skipped_already_posted ?? acct.campaign_skipped_already_posted ?? 0,
    )
    const active = Number(camp.active_groups ?? acct.campaign_active_groups ?? acct.active_groups ?? 0)
    const cycle = Number(camp.cycle ?? acct.campaign_cycle ?? 0)
    const sliceSize = acct.my_groups?.length ?? 0
    return {
      success,
      failed,
      skippedAlreadyPosted,
      skippedCooldown: Number(camp.skipped_cooldown ?? acct.skipped_cooldown ?? 0),
      skippedOther: Number(camp.skipped_other ?? acct.skipped_other ?? 0),
      active,
      cycle,
      tickMax: sliceSize || active || 1,
      sentSinceReset: Number(acct.campaign_posts_24h ?? 0),
      currentGroup: camp.current_group ?? acct.campaign_current_group ?? acct.current_group ?? '',
    }
  }

  return {
    success: Number(acct.success ?? 0),
    failed: Number(acct.failed ?? 0),
    skippedAlreadyPosted: Number(acct.skipped_already_posted ?? 0),
    skippedCooldown: Number(acct.skipped_cooldown ?? 0),
    skippedOther: Number(acct.skipped_other ?? 0),
    active: Number(acct.active_groups ?? 0),
    cycle: Number(acct.cycle ?? 0),
    tickMax: acct.my_groups?.length ?? acct.active_groups ?? 1,
    sentSinceReset: Number(acct.messages_sent_24h ?? 0),
    currentGroup: acct.current_group ?? '',
  }
}

function includeSlot(modeFilter, accountStates, postingModes, slot) {
  if (modeFilter === 'forwarding') {
    return isForwardingEnabled(accountStates, slot, postingModes)
  }
  if (modeFilter === 'campaign') {
    return isCampaignEnabled(accountStates, slot, postingModes)
  }
  return true
}

/** Per-account tick success rate (0% when the account had no send attempts this tick). */
export function accountTickSuccessRate(row, modeFilter) {
  const success = Number(row?.success) || 0
  const failed = Number(row?.failed) || 0
  const skipped = Number(row?.skippedAlreadyPosted) || 0
  const tried = modeFilter === 'forwarding' ? success + failed + skipped : success + failed
  return tried > 0 ? (success / tried) * 100 : 0
}

/** KPI success rate for fleet / All accounts (average of per-account tick rates). */
export function fleetDisplaySuccessRate(fleet) {
  return fleet?.averageSuccessRate ?? fleet?.successRate ?? '0.0'
}

/** Mean of per-account tick success rates — only accounts with send attempts this tick. */
export function averageAccountSuccessRate(perAccount, modeFilter) {
  if (!perAccount?.length) return '0.0'
  let sum = 0
  let active = 0
  for (const row of perAccount) {
    const success = Number(row?.success) || 0
    const failed = Number(row?.failed) || 0
    const skipped = Number(row?.skippedAlreadyPosted) || 0
    const tried = modeFilter === 'forwarding' ? success + failed + skipped : success + failed
    if (tried <= 0) continue
    sum += accountTickSuccessRate(row, modeFilter)
    active += 1
  }
  if (active === 0) return '0.0'
  return (sum / active).toFixed(1)
}

/**
 * Aggregate per-account worker state into fleet-wide dashboard numbers.
 * modeFilter: 'all' | 'forwarding' | 'campaign' — limits which accounts/metrics are summed.
 */
export function aggregateFleetStats(state, slots, options = {}) {
  const { postingModes = {}, modeFilter = 'all' } = options
  const accountStates = state.account_states || {}
  const masterTotal = state.total || 0
  let success = 0
  let failed = 0
  let needResend = 0
  let progressValue = 0
  let progressMax = 0
  let queueTotal = 0
  let runningCount = 0
  let sleepingCount = 0
  let rateLimitedCount = 0
  let stoppedCount = 0
  let idleCount = 0
  let hasAnyCycle = false
  let minCountdown = null
  let messagesSent24h = 0
  let skippedAlreadyPosted = 0
  let skippedCooldown = 0
  let skippedOther = 0
  const sending = []
  const perAccount = []

  for (const slot of slots) {
    if (!includeSlot(modeFilter, accountStates, postingModes, slot)) continue

    const acct = accountStates[slot]
    const loggedIn = !!state.account_info?.[slot]
    const acctStatus = state.account_status?.[slot]
    const status = getAccountStatus(acct, loggedIn, acctStatus, state.account_shutdown, slot)
    const m = featureMetrics(acct, modeFilter)

    if (modeFilter === 'forwarding') {
      queueTotal += acctStatus?.queue_depth ?? 0
    } else {
      queueTotal += acct?.my_groups?.length ?? acctStatus?.queue_depth ?? 0
    }

    if (status === 'running') runningCount += 1
    else if (status === 'sleeping') sleepingCount += 1
    else if (status === 'rate_limited') rateLimitedCount += 1
    else if (status === 'stopped') stoppedCount += 1
    else idleCount += 1

    success += m.success
    failed += m.failed
    messagesSent24h += m.sentSinceReset
    skippedAlreadyPosted += m.skippedAlreadyPosted
    skippedCooldown += m.skippedCooldown
    skippedOther += m.skippedOther
    if (modeFilter === 'forwarding') {
      needResend += m.tickRemaining ?? Math.max(0, m.active - (m.success + m.failed + m.skippedAlreadyPosted))
    } else {
      needResend += m.active
    }

    if (m.cycle > 0) {
      hasAnyCycle = true
      if (modeFilter === 'forwarding') {
        const tickTotal = m.tickTotal || m.active || m.tickMax || 0
        const tickDone = m.tickProcessed ?? (m.success + m.failed + m.skippedAlreadyPosted)
        if (tickTotal > 0) {
          progressValue += Math.min(tickTotal, tickDone)
          progressMax += tickTotal
        }
      } else {
        const sliceSize = acct?.my_groups?.length ?? masterTotal
        const processed = m.success + m.failed
        const skipped = Math.max(0, (sliceSize || masterTotal) - m.active)
        progressValue += Math.min(sliceSize || masterTotal, skipped + processed)
        progressMax += sliceSize || masterTotal
      }
    }

    const cd = acct?.next_cycle_in ?? 0
    if (cd > 0 && (minCountdown == null || cd < minCountdown)) {
      minCountdown = cd
    }

    if (acct?.running && m.currentGroup && !isHeavyRateLimit(acct)) {
      sending.push({ slot, group: m.currentGroup })
    }

    perAccount.push({
      slot,
      status,
      success: m.success,
      failed: m.failed,
      messagesSent24h: m.sentSinceReset,
      skippedAlreadyPosted: m.skippedAlreadyPosted,
      skippedCooldown: m.skippedCooldown,
      cycle: m.cycle,
      health: acct?.health_score,
      running: !!acct?.running,
    })
  }

  const processed = success + failed
  const tickTried = success + failed + skippedAlreadyPosted
  const successRate = modeFilter === 'forwarding' && tickTried > 0
    ? ((success / tickTried) * 100).toFixed(1)
    : processed > 0
      ? ((success / processed) * 100).toFixed(1)
      : '0.0'
  const averageSuccessRate = averageAccountSuccessRate(perAccount, modeFilter)

  if (progressMax <= 0) {
    progressMax = queueTotal > 0 ? queueTotal : masterTotal || 1
  }

  return {
    masterTotal,
    success,
    failed,
    messagesSent24h,
    skippedAlreadyPosted,
    skippedCooldown,
    skippedOther,
    skippedTotal: skippedAlreadyPosted + skippedCooldown + skippedOther,
    needResend,
    processed: modeFilter === 'forwarding' ? tickTried : processed,
    successRate,
    averageSuccessRate,
    progressValue: Math.min(progressMax, progressValue),
    progressMax,
    hasAnyCycle,
    runningCount,
    sleepingCount,
    rateLimitedCount,
    stoppedCount,
    idleCount,
    minCountdown: minCountdown ?? 0,
    sending,
    perAccount,
    accountCount: perAccount.length,
    modeFilter,
  }
}
