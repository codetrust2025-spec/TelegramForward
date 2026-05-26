import React, { useState, useRef, useEffect } from 'react'
import { API, COUNTRY_CODES, SAVED_PHONES } from '../config.js'
import { ButtonContent, Spinner } from '../Loader.jsx'
import { StatusBadge } from './StatusBadge.jsx'
import { MessageEditor } from './MessageEditor.jsx'
import {
  accountLabel,
  accountCardTitle,
  telegramDisplayName,
  telegramUsername,
  formatJoinedStats,
  formatTelegramMembershipTooltip,
  formatJoinStatsToday,
  formatMembershipScannedAt,
  isMembershipStale,
  formatMembershipAge,
  JOINS_TODAY_TOOLTIP,
  formatAccountStatusLabel,
  formatPhoneDisplay,
  formatCountdown,
  getAccountStatus,
  getHealthLevel,
  isHeavyRateLimit,
  isSubscriptionAccount,
} from '../utils/accountUi'
import { useConfirm } from '../context/ConfirmContext.jsx'
import { SubscriptionBadge } from './SubscriptionBadge.jsx'
import { Button } from './ui/Button.jsx'
import { MetricBlock, MetricGrid } from './ui/MetricBlock.jsx'

function AccountCardMenu({ open, onToggle, onClose, items }) {
  const ref = useRef(null)
  useEffect(() => {
    if (!open) return undefined
    function onDoc(e) {
      if (ref.current && !ref.current.contains(e.target)) onClose()
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [open, onClose])

  return (
    <div className="acct-v3-menu" ref={ref}>
      <button
        type="button"
        className="btn btn--ghost btn--sm acct-v3-menu-trigger"
        onClick={onToggle}
        aria-expanded={open}
        aria-haspopup="menu"
        title="More actions"
      >
        ⋯
      </button>
      {open && (
        <div className="acct-v3-menu-panel" role="menu">
          {items.map(item => (
            <button
              key={item.key}
              type="button"
              role="menuitem"
              className={`acct-v3-menu-item${item.danger ? ' acct-v3-menu-item--danger' : ''}`}
              onClick={item.onClick}
              disabled={item.disabled}
            >
              {item.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export function AccountMiniCard({
  slot,
  selected,
  info,
  acctState,
  accountStatus,
  switching,
  isSubscription = false,
  onSelect,
}) {
  const loggedIn = !!info
  const status = getAccountStatus(acctState, loggedIn, accountStatus)
  const statusLabel = formatAccountStatusLabel(status)
  const tgName = telegramDisplayName(info)
  const tgUser = telegramUsername(info)
  const slotLabel = accountLabel(slot)
  const displayName = loggedIn && tgName ? tgName : (loggedIn ? slotLabel : 'Empty slot')
  const isSub = isSubscription || isSubscriptionAccount(slot, null, info)
  const membership = formatJoinedStats(info)
  const membershipStale = isMembershipStale(info)

  const title = isSub
    ? `${accountCardTitle(slot, info)} · Subscription account`
    : accountCardTitle(slot, info)

  const groupsTooltip = membership
    ? formatTelegramMembershipTooltip(membership)
    : undefined

  return (
    <button
      type="button"
      className={`account-mini account-mini--v2${selected ? ' account-mini--selected' : ''} account-mini--${status}${isSub ? ' account-mini--subscription' : ''}${switching ? ' account-mini--busy' : ''}`}
      onClick={() => onSelect(slot)}
      disabled={switching}
      title={title}
      aria-current={selected ? 'true' : undefined}
      aria-label={`${slotLabel}, ${statusLabel}${tgName ? `, ${tgName}` : ''}${membership ? `, ${membership.total} joined groups` : ''}`}
    >
      <span className="account-mini-top">
        <span className="account-mini-slot">{slotLabel}</span>
        {isSub && <SubscriptionBadge variant="icon" title="Subscription account" />}
        <span className={`account-mini-status-pill account-mini-status-pill--${status}`}>
          {statusLabel}
        </span>
      </span>

      <span className="account-mini-name" title={displayName}>{displayName}</span>

      {loggedIn && tgUser && (
        <span className="account-mini-user">{tgUser}</span>
      )}

      {loggedIn && membership && (
        <span
          className={`account-mini-groups${membershipStale ? ' account-mini-groups--stale' : ''}`}
          title={groupsTooltip}
        >
          <span className="account-mini-groups-icon" aria-hidden>👥</span>
          {membership.total} groups
          {membershipStale && <span className="account-mini-groups-stale-dot" aria-hidden>·</span>}
        </span>
      )}

      {!loggedIn && (
        <span className="account-mini-hint">Tap to log in</span>
      )}
    </button>
  )
}

export function AccountCard({
  slot,
  label,
  info,
  isActive,
  isSubscription = false,
  acctRunning,
  onLogin,
  onLogout,
  onStart,
  onStop,
  onRefreshJoined,
  acctState,
  accountStatus,
  refreshingJoined,
  accountActionLoading,
  switchingAccount,
  statsWindow: _statsWindow,
  sentInWindow: _sentInWindow,
  customMessage = '',
  onMessageSaved,
}) {
  const [step, setStep] = useState('idle')
  const [countryCode, setCountryCode] = useState('+91')
  const [localNumber, setLocalNumber] = useState('')
  const [phone, setPhone] = useState('+91')
  const [otp, setOtp] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const [menuOpen, setMenuOpen] = useState(false)
  const startLoading = accountActionLoading === `${slot}:start`
  const stopLoading = accountActionLoading === `${slot}:stop`
  const heavyLimit = isHeavyRateLimit(acctState)
  const status = getAccountStatus(acctState, !!info, accountStatus)
  const health = getHealthLevel(acctState)
  const membership = formatJoinedStats(info)
  const membershipStale = isMembershipStale(info)
  const membershipAge = formatMembershipAge(info)
  const membershipTooltip = formatTelegramMembershipTooltip(membership)
  const joinToday = formatJoinStatsToday(acctState)
  const scannedAt = formatMembershipScannedAt(membership?.updated)
  const displayName = info?.name ? telegramDisplayName(info) || label : label
  const { confirm } = useConfirm()

  function resetPhoneFields() {
    setCountryCode('+91')
    setLocalNumber('')
    setPhone('+91')
  }

  function buildPhone(code, local) {
    const c = (code || '+91').trim()
    const n = (local || '').trim().replace(/[\s-]/g, '').replace(/^0+/, '')
    if (!n) return c
    return `${c}${n}`
  }

  function applyFullPhone(full) {
    const p = full.trim().replace(/[\s-]/g, '')
    const match = COUNTRY_CODES.find(c => p.startsWith(c))
    if (match) {
      setCountryCode(match)
      setLocalNumber(p.slice(match.length))
      setPhone(p)
    } else {
      setCountryCode('+91')
      setLocalNumber(p.replace(/^\+/, ''))
      setPhone(p.startsWith('+') ? p : `+${p}`)
    }
  }

  async function sendOtp() {
    const normalized = buildPhone(countryCode, localNumber)
    if (!localNumber.trim() || normalized.length < 8) {
      setError('Enter a valid phone number (e.g. 9876543210 after +91)')
      return
    }
    setLoading(true)
    setError('')
    const res = await fetch(`${API}/login/send-otp`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phone: normalized, slot }),
    })
    const data = await res.json()
    setLoading(false)
    if (data.success) {
      setPhone(normalized)
      setStep('otp')
    } else setError(data.error || 'Failed to send OTP')
  }

  async function verifyOtp() {
    if (!otp.trim()) {
      setError('Enter the OTP code from Telegram')
      return
    }
    setLoading(true)
    setError('')
    const res = await fetch(`${API}/login/verify-otp`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: otp.trim(), slot }),
    })
    const data = await res.json()
    setLoading(false)
    if (data.success) {
      setStep('idle')
      onLogin(data)
    } else setError(data.error || 'Invalid OTP')
  }

  async function doLogout() {
    const ok = await confirm({
      title: `Log out ${label}?`,
      message: 'This account will need phone login again to send messages.',
      confirmLabel: 'Log out',
      variant: 'warn',
    })
    if (!ok) return
    setLoading(true)
    setError('')
    try {
      const res = await fetch(`${API}/login/logout`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ slot }),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok || !data.success) {
        setError(data.error || 'Logout failed — try again')
        return
      }
      setStep('phone')
      resetPhoneFields()
      setOtp('')
      onLogout(slot)
    } catch (e) {
      setError(e.message || 'Logout failed')
    } finally {
      setLoading(false)
    }
  }

  async function handleStop() {
    const ok = await confirm({
      title: `Stop ${label}?`,
      message: 'The worker will stop after the current step finishes.',
      confirmLabel: 'Stop',
      cancelLabel: 'Keep running',
      variant: 'danger',
    })
    if (ok) onStop(slot)
  }

  const isSubAccount = isSubscription || isSubscriptionAccount(slot, null, info)

  async function handleRestart() {
    const ok = await confirm({
      title: `Restart ${label}?`,
      message: acctRunning
        ? 'The worker will stop and start again from the next cycle.'
        : 'Start the worker from a fresh cycle.',
      confirmLabel: 'Restart',
      variant: 'warn',
    })
    if (!ok) return
    if (acctRunning) await onStop(slot)
    onStart(slot, false)
  }

  const healthScore = acctState?.health_score != null && !Number.isNaN(Number(acctState.health_score))
    ? Math.round(Number(acctState.health_score))
    : null
  const cycleNum = acctState?.cycle > 0 ? acctState.cycle : null
  const cycleSuccess = acctState?.success ?? 0
  const cycleFailed = acctState?.failed ?? 0
  const cycleProcessed = cycleSuccess + cycleFailed
  const cycleTotal = acctState?.my_groups?.length || acctState?.active_groups || 0
  const cyclePct = cycleTotal > 0 ? Math.min(100, Math.round((cycleProcessed / cycleTotal) * 100)) : 0
  const joinsToday = joinToday?.today ?? 0
  const joinsLimit = joinToday?.limit ?? 0
  const joinsTone = joinToday?.restricted ? 'bad' : joinsLimit > 0 && joinsToday >= joinsLimit * 0.8 ? 'warn' : 'good'
  const healthTone = health === 'good' ? 'good' : health === 'warning' ? 'warn' : health === 'bad' ? 'bad' : 'neutral'
  const nextIn = acctState?.next_cycle_in > 0 ? acctState.next_cycle_in : 0
  const liveClass = status === 'running' ? 'running'
    : (status === 'sleeping' || status === 'rate_limited') ? 'waiting'
      : 'stopped'
  const currentGroup = acctState?.current_group
    ? `@${String(acctState.current_group).replace(/^@/, '')}`
    : null
  const statusSub = currentGroup && acctRunning
    ? currentGroup
    : (nextIn > 0 && (status === 'running' || status === 'sleeping'))
      ? `next in ${formatCountdown(nextIn)}`
      : null
  const hasHealth = healthScore != null && healthScore > 0
  const joinsPct = joinsLimit > 0 ? Math.round((joinsToday / joinsLimit) * 100) : null
  const cycleDisplay = cycleTotal > 0
    ? `${cycleProcessed}/${cycleTotal}`
    : (cycleNum ? `#${cycleNum}` : null)

  const metaParts = []
  if (membership) {
    metaParts.push(`${membership.total} groups`)
    metaParts.push(`${membership.groups}g / ${membership.channels}c`)
  }
  if (scannedAt) metaParts.push(`scanned ${membershipAge || scannedAt}`)
  if (membershipStale) metaParts.push('stale')
  const metaLine = metaParts.join(' · ')

  const cardClass = [
    'account-card',
    isActive ? 'account-card--active' : '',
    `account-card--${status}`,
    heavyLimit ? 'account-card--sleep' : '',
    isSubAccount ? 'account-card--subscription' : '',
  ].filter(Boolean).join(' ')

  return (
    <article className={`${cardClass} account-card--dense account-card--v3 account-card--live account-card--live-${liveClass}`}>
      {info ? (
        <>
          <div className="acct-v3-shine" aria-hidden />
          <header className="acct-v3-header">
            <div className="acct-v3-identity">
              <h3 className="acct-v3-name">{displayName}</h3>
              <p className="acct-v3-phone-row">
                {info.phone && <span>{formatPhoneDisplay(info.phone)}</span>}
                {isSubAccount && <SubscriptionBadge variant="dot" title="Subscription account" />}
              </p>
            </div>
            <div className="acct-v3-status-wrap">
              <StatusBadge
                status={status}
                pulse={status === 'running'}
                label={
                  status === 'sleeping' ? 'Waiting'
                    : status === 'rate_limited' ? 'Flood'
                      : undefined
                }
              />
              {statusSub && (
                <span className="acct-v3-status-sub">{statusSub}</span>
              )}
            </div>
          </header>

          <div className="acct-v3-body" onClick={e => e.stopPropagation()}>
            <MetricGrid columns={2} className="acct-v3-grid">
              {cycleTotal > 0 ? (
                <MetricBlock
                  className="acct-v3-cell"
                  label="Send slice"
                  value={cycleTotal}
                  tone="neutral"
                  title="Groups assigned to this account for posting (share of master list, minus dead names). Cycle bar uses this count."
                />
              ) : null}
              {membership != null || refreshingJoined ? (
                <MetricBlock
                  className="acct-v3-cell"
                  label="On Telegram"
                  value={refreshingJoined ? '…' : membership.total}
                  tone={membershipStale ? 'warn' : 'neutral'}
                  title={membershipTooltip}
                />
              ) : null}
              {joinToday ? (
                <MetricBlock
                  className="acct-v3-cell"
                  label="Joins"
                  value={`${joinToday.today}${joinToday.limit != null ? `/${joinToday.limit}` : ''}`}
                  progress={joinsPct}
                  tone={joinsTone}
                  title={JOINS_TODAY_TOOLTIP}
                />
              ) : null}
              {cycleNum != null ? (
                <MetricBlock
                  className={`acct-v3-cell${!hasHealth ? ' acct-v3-cell--span' : ''}`}
                  label="Cycle"
                  value={cycleDisplay || `#${cycleNum}`}
                  progress={cycleTotal > 0 ? cyclePct : null}
                  tone={cyclePct >= 70 ? 'good' : cyclePct >= 35 ? 'warn' : 'neutral'}
                  title={cycleNum
                    ? `${cycleSuccess} OK · ${cycleFailed} fail · cycle #${cycleNum}`
                    : undefined}
                />
              ) : null}
              {hasHealth ? (
                <MetricBlock
                  className="acct-v3-cell"
                  label="Health"
                  value={`${healthScore}%`}
                  progress={healthScore}
                  tone={healthTone}
                  title={`Health score ${healthScore}%`}
                />
              ) : null}
            </MetricGrid>
            {(refreshingJoined || metaLine) && (
              <p className="acct-v3-meta">
                {refreshingJoined ? (
                  <span className="acct-v3-meta-loading"><Spinner size={10} /> Scanning…</span>
                ) : metaLine}
              </p>
            )}
          </div>

          <footer className="acct-v3-actions" onClick={e => e.stopPropagation()}>
            {!acctRunning ? (
              <Button
                variant="success"
                size="sm"
                className="acct-v3-btn-action"
                onClick={() => onStart(slot, false)}
                disabled={startLoading}
                loading={startLoading}
                loadingLabel="…"
              >
                <span className="acct-v3-btn-icon" aria-hidden>▶</span> Start
              </Button>
            ) : (
              <Button
                variant="danger"
                size="sm"
                className="acct-v3-btn-action acct-v3-btn-stop"
                onClick={handleStop}
                disabled={stopLoading}
                loading={stopLoading}
                loadingLabel="…"
              >
                <span className="acct-v3-btn-icon" aria-hidden>⏹</span> Stop
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              className="acct-v3-btn-action acct-v3-btn-restart"
              onClick={handleRestart}
              disabled={startLoading || stopLoading}
            >
              ↻ Restart
            </Button>
            <AccountCardMenu
              open={menuOpen}
              onToggle={() => setMenuOpen(v => !v)}
              onClose={() => setMenuOpen(false)}
              items={[
                {
                  key: 'rescan',
                  label: refreshingJoined ? 'Scanning…' : 'Rescan membership',
                  onClick: () => { setMenuOpen(false); onRefreshJoined(slot) },
                  disabled: refreshingJoined,
                },
                {
                  key: 'logout',
                  label: 'Log out',
                  danger: true,
                  onClick: () => { setMenuOpen(false); doLogout() },
                  disabled: loading || acctRunning,
                },
              ]}
            />
          </footer>

          {/* ── Per-account message editor ── */}
          <div className="acct-v3-message-editor" onClick={e => e.stopPropagation()}>
            <MessageEditor
              slot={slot}
              customMessage={customMessage}
              onSaved={onMessageSaved || (() => {})}
            />
          </div>
        </>
      ) : step === 'idle' ? (
        <div className="account-card-login">
          <p className="stat-hint">Not logged in</p>
          <button type="button" className="btn btn--success" onClick={() => { resetPhoneFields(); setStep('phone') }}>
            + Login
          </button>
        </div>
      ) : step === 'phone' ? (
        <div className="account-card-form" onClick={e => e.stopPropagation()}>
          <label className="field-label">Phone number</label>
          <div className="field-row">
            <select className="input input--select" value={countryCode} onChange={e => setCountryCode(e.target.value)}>
              {COUNTRY_CODES.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
            <input
              className="input"
              type="tel"
              placeholder="9876543210"
              value={localNumber}
              onChange={e => setLocalNumber(e.target.value.replace(/\D/g, ''))}
              onKeyDown={e => e.key === 'Enter' && localNumber.trim() && sendOtp()}
              autoFocus
            />
          </div>
          <select className="input" value="" onChange={e => { if (e.target.value) applyFullPhone(e.target.value) }}>
            <option value="">Quick pick saved number…</option>
            {SAVED_PHONES.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
          {error && <p className="field-error">{error}</p>}
          <div className="btn-row">
            <button type="button" className="btn btn--primary" onClick={sendOtp} disabled={loading || !localNumber.trim()}>
              <ButtonContent loading={loading} loadingLabel="Sending…">Send OTP</ButtonContent>
            </button>
            <button type="button" className="btn btn--ghost" onClick={() => { resetPhoneFields(); setStep('idle'); setError('') }}>Cancel</button>
          </div>
        </div>
      ) : (
        <div className="account-card-form" onClick={e => e.stopPropagation()}>
          <p className="field-hint">OTP sent to <strong>{phone}</strong></p>
          <input className="input" placeholder="Enter OTP" value={otp} onChange={e => setOtp(e.target.value)} onKeyDown={e => e.key === 'Enter' && verifyOtp()} />
          {error && <p className="field-error">{error}</p>}
          <div className="btn-row">
            <button type="button" className="btn btn--success" onClick={verifyOtp} disabled={loading || !otp}>
              <ButtonContent loading={loading} loadingLabel="Verifying…">Verify</ButtonContent>
            </button>
            <button type="button" className="btn btn--ghost" onClick={() => { resetPhoneFields(); setStep('phone'); setError('') }}>← Back</button>
          </div>
        </div>
      )}
    </article>
  )
}
