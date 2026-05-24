import React, { useEffect, useState } from 'react'
import { API } from '../config.js'
import { ButtonContent } from '../Loader.jsx'
import { accountLabel } from '../utils/accountUi.js'
import { MetricBlock, MetricGrid } from './ui/MetricBlock.jsx'

function windowLabel(dailyStats, scopeAccount) {
  const who = scopeAccount ? accountLabel(scopeAccount) : 'All accounts'
  if (dailyStats?.window === 'since_reset' && dailyStats?.reset_at) {
    try {
      const d = new Date(dailyStats.reset_at)
      if (!Number.isNaN(d.getTime())) {
        return `${who} · since reset · ${d.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}`
      }
    } catch { /* ignore */ }
    return `${who} · since last reset`
  }
  return `${who} · rolling last 24 hours`
}

/**
 * Today reach + inbox/forward counters with global or per-account reset.
 */
export function DailyStatsPanel({
  dailyStats,
  accountSlots,
  accountInfo,
  accountStates,
  onDailyStatsUpdate,
  onConfirmReset,
  scopeAccount = null,
}) {
  const [resetting, setResetting] = useState(null)
  const [toast, setToast] = useState(null)

  useEffect(() => {
    if (!toast) return undefined
    const id = window.setTimeout(() => setToast(null), 3200)
    return () => clearTimeout(id)
  }, [toast])

  const scoped = scopeAccount ? (dailyStats?.per_account?.[scopeAccount] || {}) : null
  const g = dailyStats?.global || {}
  const contacts = scoped ? (scoped.contacts ?? 0) : (g.contacts ?? 0)
  const incoming = scoped ? (scoped.incoming ?? 0) : (g.incoming ?? 0)
  const outgoing = scoped ? (scoped.outgoing ?? 0) : (g.outgoing ?? 0)
  const forwarded = scoped ? (scoped.forwarded ?? 0) : (g.forwarded ?? 0)
  const joinedToday = scopeAccount
    ? (Number(accountStates?.[scopeAccount]?.join_stats?.joins_today) || 0)
    : accountSlots.reduce((sum, slot) => {
        const joinStats = accountStates?.[slot]?.join_stats
        return sum + (Number(joinStats?.joins_today) || 0)
      }, 0)
  const joinLimit = scopeAccount
    ? (Number(accountStates?.[scopeAccount]?.join_stats?.joins_daily_limit) || 0)
    : accountSlots.reduce((sum, slot) => {
        const limit = accountStates?.[slot]?.join_stats?.joins_daily_limit
        return sum + (Number(limit) || 0)
      }, 0)

  async function handleReset(scope = 'global', accountId = null) {
    const resetKey = scope === 'account' ? accountId : 'global'
    if (resetting) return

    const label = scope === 'account' ? accountLabel(accountId) : null
    const ok = await onConfirmReset({ scope, accountId, accountLabel: label })
    if (!ok) return

    setResetting(resetKey)
    try {
      const body = scope === 'account'
        ? { scope: 'account', account_id: accountId }
        : { scope: 'global' }
      const res = await fetch(`${API}/stats/reset`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok || data.status === 'error') {
        const msg = data.message || data.error || 'Could not reset stats'
        setToast(msg)
        return
      }
      if (data?.daily_stats && onDailyStatsUpdate) {
        onDailyStatsUpdate(data.daily_stats, data)
      }
      setToast(
        scope === 'account'
          ? `${label} stats reset successfully`
          : 'Stats reset successfully',
      )
    } finally {
      setResetting(null)
    }
  }

  const perAccount = dailyStats?.per_account || {}
  const ranked = [...accountSlots]
    .map(slot => ({ slot, ...(perAccount[slot] || {}) }))
    .sort((a, b) => {
      const ta = (a.contacts || 0) + (a.incoming || 0) + (a.outgoing || 0) + (a.forwarded || 0)
      const tb = (b.contacts || 0) + (b.incoming || 0) + (b.outgoing || 0) + (b.forwarded || 0)
      return tb - ta
    })
    .filter(r => (r.contacts || 0) + (r.incoming || 0) + (r.outgoing || 0) + (r.forwarded || 0) > 0)

  const globalResetting = resetting === 'global'
  const accountResetting = scopeAccount && resetting === scopeAccount
  const statsTitle = scopeAccount ? 'Today reach' : 'Fleet today reach'

  return (
    <section className="daily-stats-panel" aria-label={scopeAccount ? 'Account today reach' : 'Fleet today reach and daily counters'}>
      <header className="daily-stats-header">
        <div>
          <h3 className="daily-stats-title">{statsTitle}</h3>
          <p className="daily-stats-sub">{windowLabel(dailyStats, scopeAccount)}</p>
        </div>
        <button
          type="button"
          className="btn btn--warn btn--sm daily-stats-reset-btn"
          onClick={() => (scopeAccount ? handleReset('account', scopeAccount) : handleReset('global'))}
          disabled={!!resetting}
          title={scopeAccount
            ? `Reset daily counters for ${accountLabel(scopeAccount)}`
            : 'Reset all daily counters to zero from now'}
        >
          <ButtonContent loading={scopeAccount ? accountResetting : globalResetting} loadingLabel="Resetting…">
            Reset 24 Hours
          </ButtonContent>
        </button>
      </header>

      <MetricGrid columns={4} className="daily-stats-grid">
        <MetricBlock label="Contacts" value={contacts} tone="success" title="Unique contacts with at least one DM in this window" />
        <MetricBlock label="Incoming" value={incoming} title="Incoming private messages" />
        <MetricBlock label="Outgoing" value={outgoing} title="Outgoing private messages (excludes in-flight)" />
        <MetricBlock label="Forwarded" value={forwarded} tone="success" title="Successful group forwards in this window" />
        <MetricBlock
          label="Joined since reset"
          value={joinedToday}
          sub={joinLimit > 0
            ? `${joinedToday}/${joinLimit}${scopeAccount ? ' daily limit' : ' fleet daily limit'}`
            : (scopeAccount ? 'This account' : 'All accounts combined')}
          tone="success"
          title={scopeAccount
            ? 'New groups joined by this account in this stats window.'
            : 'New groups joined by automation across all accounts in this stats window. This does not include old Telegram memberships.'}
        />
      </MetricGrid>

      {!scopeAccount && ranked.length > 0 && (
        <details className="daily-stats-per-account">
          <summary>Per account breakdown</summary>
          <ul className="daily-stats-account-list">
            {ranked.map(row => {
              const rowResetting = resetting === row.slot
              return (
                <li key={row.slot} className="daily-stats-account-row">
                  <span className="daily-stats-account-name">{accountLabel(row.slot)}</span>
                  <span className="daily-stats-account-metrics">
                    {row.contacts ?? 0} contacts · {row.incoming ?? 0} in · {row.outgoing ?? 0} out · {row.forwarded ?? 0} fwd
                  </span>
                  <button
                    type="button"
                    className="btn btn--ghost btn--sm daily-stats-account-reset"
                    onClick={() => handleReset('account', row.slot)}
                    disabled={!!resetting}
                    title={`Reset 24-hour stats for ${accountLabel(row.slot)} only`}
                  >
                    <ButtonContent loading={rowResetting} loadingLabel="…">
                      Reset
                    </ButtonContent>
                  </button>
                </li>
              )
            })}
          </ul>
        </details>
      )}

      <p className="daily-stats-footnote">
        {scopeAccount
          ? 'Account counters only — chat history and sessions are kept. New activity for this account counts from the reset moment.'
          : 'Fleet-wide calculated stats only — chat history and accounts are kept. New activity across all accounts counts from the reset moment.'}
      </p>

      {toast && (
        <div className="crm-toast daily-stats-toast" role="status" aria-live="polite">
          {toast}
        </div>
      )}
    </section>
  )
}
