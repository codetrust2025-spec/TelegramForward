/**
 * Copy for the stats-reset confirmation modal (Fleet / account scope).
 */

const CLEARED_ITEMS = [
  'Forward posts and campaign reach counters (since reset or start of today IST)',
  'Current tick sent, skipped, and failed (live display)',
  'Campaign cycle success / fail counters on screen',
  'Joined-since-reset count (join baseline)',
  'Forward tick group rotation pool (starts a fresh round)',
]

const KEPT_ITEMS = [
  'Telegram accounts, sessions, and login',
  'Joined groups, chats, and master group list',
  'Message templates, posting mode, and 24/7 settings',
  'Inbox messages, stored logs, and CRM contacts',
  'Running workers (forwarding / campaign are not stopped)',
]

export function statsResetConfirmOptions({ scope = 'global', accountLabel: acctLabel = null } = {}) {
  const isAccount = scope === 'account' && acctLabel

  return {
    title: isAccount ? `Reset stats for ${acctLabel}?` : 'Reset today?',
    message: isAccount
      ? `This resets display counters for ${acctLabel} from now until midnight IST. Other accounts are unchanged.`
      : 'This resets fleet-wide display counters from now until midnight IST. Counters also auto-reset at midnight IST each day.',
    cleared: [...CLEARED_ITEMS],
    kept: [...KEPT_ITEMS],
    confirmLabel: 'Reset now',
    cancelLabel: 'Cancel',
    variant: 'warn',
  }
}
