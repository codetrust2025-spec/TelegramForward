import { getAccountStatus, isHeavyRateLimit } from './accountUi'

/**
 * Aggregate per-account worker state into fleet-wide dashboard numbers.
 */
export function aggregateFleetStats(state, slots) {
  const masterTotal = state.total || 0
  let success = 0
  let failed = 0
  let needResend = 0
  let progressValue = 0
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
    const acct = state.account_states?.[slot]
    const loggedIn = !!state.account_info?.[slot]
    const acctStatus = state.account_status?.[slot]
    const status = getAccountStatus(acct, loggedIn, acctStatus)

    queueTotal += acctStatus?.queue_depth ?? 0

    if (status === 'running') runningCount += 1
    else if (status === 'sleeping') sleepingCount += 1
    else if (status === 'rate_limited') rateLimitedCount += 1
    else if (status === 'stopped') stoppedCount += 1
    else idleCount += 1

    const s = acct?.success ?? 0
    const f = acct?.failed ?? 0
    const active = acct?.active_groups ?? 0
    const sliceSize = acct?.my_groups?.length ?? 0
    const cycle = acct?.cycle ?? 0

    success += s
    failed += f
    messagesSent24h += acct?.messages_sent_24h ?? 0
    skippedAlreadyPosted += acct?.skipped_already_posted ?? 0
    skippedCooldown += acct?.skipped_cooldown ?? 0
    skippedOther += acct?.skipped_other ?? 0
    needResend += active
    queueTotal += sliceSize

    if (cycle > 0) {
      hasAnyCycle = true
      const processed = s + f
      const skipped = Math.max(0, (sliceSize || masterTotal) - active)
      progressValue += Math.min(sliceSize || masterTotal, skipped + processed)
    }

    const cd = acct?.next_cycle_in ?? 0
    if (cd > 0 && (minCountdown == null || cd < minCountdown)) {
      minCountdown = cd
    }

    if (acct?.running && acct?.current_group && !isHeavyRateLimit(acct)) {
      sending.push({ slot, group: acct.current_group })
    }

    perAccount.push({
      slot,
      status,
      success: s,
      failed: f,
      messagesSent24h: acct?.messages_sent_24h ?? 0,
      skippedAlreadyPosted: acct?.skipped_already_posted ?? 0,
      skippedCooldown: acct?.skipped_cooldown ?? 0,
      cycle,
      health: acct?.health_score,
      running: !!acct?.running,
    })
  }

  const processed = success + failed
  const successRate = processed > 0 ? ((success / processed) * 100).toFixed(1) : '0.0'
  const progressMax = queueTotal > 0 ? queueTotal : masterTotal || 1

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
    processed,
    successRate,
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
    accountCount: slots.length,
  }
}
