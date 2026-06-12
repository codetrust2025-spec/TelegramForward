/** Tooltip copy for Fleet today reach metrics (Forwarding tab). */

export const FORWARDING_METRIC_HELP = {
  forwardPosts:
    'Cumulative successful posts to joined groups since midnight IST (or since a manual reset today). Persists across ticks and refresh. Compare with “Current tick sent” for live batch progress.',
  runningNow:
    'How many accounts are actively forwarding right now (24/7 loop or a forward job). 0 = all stopped or resting between ticks.',
  currentTickSent:
    'Live batch only — resets when a new forward tick starts. Sent = successes this tick; skipped = already posted there; failed = errors. Not the same as “Forward posts (since reset)”.',
  currentTickAccount:
    'This account’s current forward batch only. Sent / skipped / failed apply to the active tick, not since reset.',
  joinedSinceReset:
    'New groups joined by automation today (IST calendar day, or since a manual reset). The limit is the fleet daily join cap (sum of per-account limits).',
  joinedSinceResetAccount:
    'New groups this account joined today (IST) or since a manual reset. Limit is this account’s daily join cap.',
}
