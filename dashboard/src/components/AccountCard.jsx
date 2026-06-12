import React, { useState, useRef, useEffect } from 'react'
import { API, COUNTRY_CODES, SAVED_PHONES } from '../config.js'
import { ButtonContent, Spinner, InlineLoader } from '../Loader.jsx'
import { StatusBadge } from './StatusBadge.jsx'
import { MessageEditor } from './MessageEditor.jsx'
import { PostingModePanel } from './PostingModePanel.jsx'
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
  formatAccountMiniStatusLabel,
  formatPhoneDisplay,
  formatCountdown,
  getAccountStatus,
  getHealthLevel,
  isHeavyRateLimit,
  isCampaignEnabled,
  isForwardingEnabled,
  isSubscriptionAccount,
  accountShutdownMapForSlot,
  isAccountOnShutdown,
  accountPrimaryMode,
} from '../utils/accountUi'
import { AccountPrimaryActions } from './AccountPrimaryActions.jsx'
import { useConfirm } from '../context/ConfirmContext.jsx'
import { SubscriptionBadge } from './SubscriptionBadge.jsx'
import { Button } from './ui/Button.jsx'
import { MetricBlock, MetricGrid } from './ui/MetricBlock.jsx'
import { AccountNameEditor } from './AccountNameEditor.jsx'
import { AccountModeSwitcher } from './AccountModeSwitcher.jsx'

export function AccountMiniCard({
  slot,
  selected,
  info,
  acctState,
  accountStatus,
  accountShutdown,
  postingModes = {},
  accountStates = {},
  switchingAccount = null,
  isSubscription = false,
  onSelect,
  onRenamed,
}) {
  const loggedIn = !!info
  const isSwitching = switchingAccount === slot
  const switchPending = switchingAccount != null && switchingAccount !== slot
  const gridLocked = switchingAccount != null
  const shutdownMap = accountShutdownMapForSlot(accountShutdown, slot)
  const status = getAccountStatus(acctState, loggedIn, accountStatus, shutdownMap, slot)
  const statusLabel = formatAccountMiniStatusLabel(status)
  const statusLabelFull = formatAccountStatusLabel(status)
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
  const campOn = isCampaignEnabled(accountStates, slot, postingModes)
  const fwdOn = isForwardingEnabled(accountStates, slot, postingModes)

  function selectSlot() {
    if (gridLocked) return
    onSelect(slot)
  }

  return (
    <div
      role="button"
      tabIndex={gridLocked ? -1 : 0}
      className={`account-mini account-mini--v2${selected ? ' account-mini--selected' : ''} account-mini--${status}${status === 'shutdown' ? ' account-mini--shutdown' : ''}${isSub ? ' account-mini--subscription' : ''}${isSwitching ? ' account-mini--switching' : ''}${switchPending ? ' account-mini--switch-pending' : ''}`}
      onClick={selectSlot}
      onKeyDown={e => {
        if (gridLocked) return
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          selectSlot()
        }
      }}
      title={title}
      aria-current={selected ? 'true' : undefined}
      aria-busy={isSwitching ? 'true' : undefined}
      aria-label={`${slotLabel}, ${statusLabel}${tgName ? `, ${tgName}` : ''}${membership ? `, ${membership.total} joined groups` : ''}${isSwitching ? ', loading' : ''}`}
    >
      {isSwitching && (
        <span className="account-mini-switch-overlay" aria-hidden>
          <Spinner size={18} />
        </span>
      )}
      <span className="account-mini-top">
        <span className="account-mini-top-row">
          <span className="account-mini-slot">{slotLabel}</span>
          {isSub && <SubscriptionBadge variant="icon" title="Subscription account" />}
          <span
            className={`account-mini-status-pill account-mini-status-pill--${status}`}
            title={statusLabelFull}
          >
            {statusLabel}
          </span>
        </span>
        <span className="account-mini-top-row account-mini-top-row--mode">
          {fwdOn ? (
            <span className="account-mini-mode-pill account-mini-mode-pill--forward" title="Forwarding enabled">
              Forward
            </span>
          ) : campOn ? (
            <span className="account-mini-mode-pill" title="Campaign enabled">
              Campaign
            </span>
          ) : null}
          {!campOn && !fwdOn && (
            <span className="account-mini-mode-pill account-mini-mode-pill--muted" title="No features enabled">
              Off
            </span>
          )}
        </span>
      </span>

      {loggedIn ? (
        <AccountNameEditor slot={slot} info={info} onRenamed={onRenamed} compact selected={selected} />
      ) : (
        <span className="account-mini-name" title={displayName}>{displayName}</span>
      )}

      <span
        className={`account-mini-user${tgUser ? '' : ' account-mini-user--empty'}`}
        aria-hidden={!tgUser}
      >
        {tgUser || '\u00a0'}
      </span>

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
    </div>
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
  accountShutdown,
  forwardJob = null,
  refreshingJoined,
  accountActionLoading,
  switchingAccount,
  statsWindow: _statsWindow,
  sentInWindow: _sentInWindow,
  customMessage = '',
  onMessageSaved,
  postingModeConfig,
  postingModes = {},
  accountStates = {},
  onPostingModeUpdated,
  setupFilter = 'all',
  workspaceMode = null,
  compactSetup = false,
  loginTab = false,
  onOpenSetupTab,
  onRenamed,
}) {
  const [step, setStep] = useState('idle')
  const [nameEditOpen, setNameEditOpen] = useState(false)
  const [countryCode, setCountryCode] = useState('+91')
  const [localNumber, setLocalNumber] = useState('')
  const [phone, setPhone] = useState('+91')
  const [otp, setOtp] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const startLoading = accountActionLoading === `${slot}:start`
  const stopLoading = accountActionLoading === `${slot}:stop`
  const campStartLoading = accountActionLoading === `${slot}:campaign:start`
  const campStopLoading = accountActionLoading === `${slot}:campaign:stop`
  const fwdStartLoading = accountActionLoading === `${slot}:forwarding:start`
  const fwdStopLoading = accountActionLoading === `${slot}:forwarding:stop`
  const heavyLimit = isHeavyRateLimit(acctState)
  const shutdownMap = accountShutdownMapForSlot(accountShutdown, slot)
  const onShutdown = isAccountOnShutdown(shutdownMap, slot)
  const status = getAccountStatus(acctState, !!info, accountStatus, shutdownMap, slot)
  const health = getHealthLevel(acctState)
  const membership = formatJoinedStats(info)
  const membershipStale = isMembershipStale(info)
  const membershipAge = formatMembershipAge(info)
  const membershipTooltip = formatTelegramMembershipTooltip(membership)
  const joinToday = formatJoinStatsToday(acctState)
  const scannedAt = formatMembershipScannedAt(membership?.updated)
  const displayName = info ? (telegramDisplayName(info) || label) : label
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

  async function loginFetch(path, body, timeoutMs = 90000) {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), timeoutMs)
    try {
      const res = await fetch(`${API}${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(body),
        signal: controller.signal,
      })
      let data = {}
      try {
        data = await res.json()
      } catch {
        data = {}
      }
      if (!res.ok && !data.error) {
        data.error = data.detail || `Request failed (${res.status})`
      }
      return data
    } catch (e) {
      if (e?.name === 'AbortError') {
        return { success: false, error: 'Request timed out. Check your connection and try again.' }
      }
      return { success: false, error: e?.message || 'Network error — try again.' }
    } finally {
      clearTimeout(timer)
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
    try {
      const data = await loginFetch('/login/send-otp', { phone: normalized, slot })
      if (data.success) {
        setPhone(normalized)
        setStep('otp')
      } else setError(data.error || 'Failed to send OTP')
    } finally {
      setLoading(false)
    }
  }

  async function verifyOtp() {
    if (!otp.trim()) {
      setError('Enter the OTP code from Telegram')
      return
    }
    setLoading(true)
    setError('')
    try {
      const data = await loginFetch('/login/verify-otp', {
        code: otp.trim(),
        slot,
        workspace_mode: workspaceMode || undefined,
      })
      if (data.success) {
        setStep('idle')
        onLogin(data)
      } else setError(data.error || 'Invalid OTP')
    } finally {
      setLoading(false)
    }
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
      message: anyRunning
        ? 'Stop all features and start enabled campaign + forwarding again.'
        : 'Start all enabled features.',
      confirmLabel: 'Restart',
      variant: 'warn',
    })
    if (!ok) return
    if (anyRunning) await onStop(slot)
    onStart(slot, false)
  }

  const healthScore = acctState?.health_score != null && !Number.isNaN(Number(acctState.health_score))
    ? Math.round(Number(acctState.health_score))
    : null
  const campRt = acctState?.campaign || {}
  const fwdRt = acctState?.forwarding || {}
  const campRunning = !!(campRt.running ?? acctState?.campaign_running)
  const fwdDispatch = (
    postingModeConfig?.forwarding?.forward_dispatch
    || postingModes?.[slot]?.forwarding?.forward_dispatch
    || 'auto'
  )
  const isManualForward = fwdDispatch !== 'auto'
  const forwardCycleRunning = forwardJob?.status === 'running'
  const fwdRunning = isManualForward
    ? forwardCycleRunning
    : !!(fwdRt.running ?? acctState?.forwarding_running)
  const anyRunning = campRunning || fwdRunning || acctRunning

  const nextIn = acctState?.next_cycle_in > 0 ? acctState.next_cycle_in : 0
  const currentGroup = acctState?.current_group
    ? `@${String(acctState.current_group).replace(/^@/, '')}`
    : null
  const statusSub = currentGroup && anyRunning
    ? currentGroup
    : (nextIn > 0 && (status === 'running' || status === 'sleeping'))
      ? `Next send in ${formatCountdown(nextIn)}`
      : null

  const campCycle = campRt.cycle ?? acctState?.campaign_cycle ?? 0
  const campSuccess = campRt.success ?? 0
  const campFailed = campRt.failed ?? 0
  const campTotal = campRt.active_groups ?? acctState?.my_groups?.length ?? 0
  const campProcessed = campSuccess + campFailed

  const fwdCycle = fwdRt.cycle ?? acctState?.forwarding_cycle ?? 0
  const fwdSuccess = fwdRt.success ?? 0
  const fwdFailed = fwdRt.failed ?? 0
  const fwdSkipped = fwdRt.skipped_already_posted ?? 0
  const fwdTotal = fwdRt.active_groups ?? 0
  const fwdJoined = fwdRt.forward_joined_total ?? acctState?.forward_joined_total ?? 0
  const fwdProcessed = fwdSuccess + fwdFailed + fwdSkipped
  const fwdBatch = fwdRt.forward_batch ?? acctState?.forward_batch ?? 0
  const fwdBatchTotal = fwdRt.forward_batch_total ?? acctState?.forward_batch_total ?? 0

  async function startRelogin() {
    const ok = await confirm({
      title: `Re-login ${label}?`,
      message: 'You will log out this slot, then enter phone + OTP again. Use this if sends fail or the session broke.',
      confirmLabel: 'Continue',
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
        setError(data.error || 'Could not log out — try again')
        return
      }
      resetPhoneFields()
      setOtp('')
      setStep('phone')
      onLogout(slot)
    } catch (e) {
      setError(e.message || 'Could not log out')
    } finally {
      setLoading(false)
    }
  }

  const accountMode = accountPrimaryMode(accountStates, slot, postingModes)
  const campOn = isCampaignEnabled(accountStates, slot, postingModes)
  const fwdOn = isForwardingEnabled(accountStates, slot, postingModes)
  const deskLabel = campOn && fwdOn
    ? 'Forward + Campaign'
    : fwdOn
      ? 'Forward desk'
      : campOn
        ? 'Campaign desk'
        : 'No desk selected'

  if (loginTab && info) {
    const statusLine = statusSub
      || (status === 'running' ? 'Sending messages now'
        : status === 'sleeping' || status === 'rate_limited' ? formatAccountStatusLabel(status)
          : 'Not sending right now')

    return (
      <article className="account-card account-card--login-manage account-card--dense account-card--v3">
        <header className="acct-login-manage__header">
          <div className="acct-login-manage__identity">
            <AccountNameEditor
                slot={slot}
                info={info}
                onRenamed={onRenamed}
                startEditing={nameEditOpen}
                onEditingChange={open => { if (!open) setNameEditOpen(false) }}
              />
            <p className="acct-v3-phone-row">
              {info.phone && <span>{formatPhoneDisplay(info.phone)}</span>}
              {isSubAccount && <SubscriptionBadge variant="dot" title="Subscription account" />}
            </p>
          </div>
          <StatusBadge
            status={status}
            pulse={status === 'running'}
            label={
              status === 'sleeping' ? 'Waiting'
                : status === 'rate_limited' ? 'Limited'
                  : undefined
            }
          />
        </header>

        <div className="acct-login-manage__body">
          <p className="acct-login-manage__status">{statusLine}</p>
          <p className="acct-login-manage__desk">
            <span className="acct-login-manage__desk-label">Assigned to</span>
            <strong>{deskLabel}</strong>
          </p>
          {membership && (
            <p className="acct-login-manage__meta">
              {membership.total} groups on Telegram
              {joinToday ? ` · ${joinToday.today}/${joinToday.limit ?? '—'} joins today` : ''}
            </p>
          )}

          <div className="acct-login-manage__mode">
            <p className="field-label">Change desk</p>
            <AccountModeSwitcher
              slot={slot}
              postingModeConfig={postingModeConfig || acctState?.posting_mode_config}
              postingModes={postingModes}
              accountStates={accountStates}
              onUpdated={onPostingModeUpdated}
              className="acct-v3-mode-switch"
            />
          </div>

          {error && <p className="field-error">{error}</p>}

          <div className="acct-login-manage__actions">
            <button
              type="button"
              className="btn btn--ghost"
              onClick={() => setNameEditOpen(true)}
            >
              Rename
            </button>
            <button
              type="button"
              className="btn btn--primary"
              onClick={startRelogin}
              disabled={loading}
            >
              <ButtonContent loading={loading} loadingLabel="Working…">Re-login (phone + OTP)</ButtonContent>
            </button>
            <button
              type="button"
              className="btn btn--ghost btn--danger-text"
              onClick={doLogout}
              disabled={loading || anyRunning}
              title={anyRunning ? 'Stop the account on the Setup tab before logging out' : undefined}
            >
              Log out
            </button>
          </div>

          {onOpenSetupTab && (
            <p className="acct-login-manage__next">
              Ready to send?{' '}
              <button type="button" className="accounts-login-guide__link" onClick={onOpenSetupTab}>
                Open Setup tab →
              </button>
            </p>
          )}
        </div>
      </article>
    )
  }

  const uiFilter = workspaceMode || setupFilter
  const showCampaignUi = uiFilter === 'all' || uiFilter === 'campaign'
  const showForwardingUi = uiFilter === 'all' || uiFilter === 'forwarding'
  const fwdCfg = postingModeConfig?.forwarding || acctState?.posting_mode_config?.forwarding || {}
  const forwardSourceType = fwdCfg.source_type === 'telegram_post' ? 'telegram_post' : 'template'
  const primaryMode = workspaceMode || accountPrimaryMode(accountStates, slot, postingModes)
  const modeMismatch = workspaceMode && accountMode !== 'off' && accountMode !== workspaceMode
  const showMessageEditor = primaryMode === 'campaign'
    || (primaryMode === 'forwarding' && forwardSourceType === 'template')
  const joinsToday = joinToday?.today ?? 0
  const joinsLimit = joinToday?.limit ?? 0
  const joinsTone = joinToday?.restricted ? 'bad' : joinsLimit > 0 && joinsToday >= joinsLimit * 0.8 ? 'warn' : 'good'
  const healthTone = health === 'good' ? 'good' : health === 'warning' ? 'warn' : health === 'bad' ? 'bad' : 'neutral'
  const liveClass = status === 'running' ? 'running'
    : (status === 'sleeping' || status === 'rate_limited') ? 'waiting'
      : 'stopped'
  const hasHealth = healthScore != null && healthScore > 0
  const joinsPct = joinsLimit > 0 ? Math.round((joinsToday / joinsLimit) * 100) : null

  const metaParts = []
  if (membership) {
    metaParts.push(`${membership.total} groups`)
    metaParts.push(`${membership.groups}g / ${membership.channels}c`)
  }
  if (scannedAt) metaParts.push(`scanned ${membershipAge || scannedAt}`)
  if (membershipStale) metaParts.push('stale')
  const metaLine = metaParts.join(' · ')

  const campStatLabel = campRunning ? 'Running' : 'Stopped'
  const campStatDetail = campTotal > 0
    ? `${campProcessed}/${campTotal} sent · cycle ${campCycle || '—'}`
    : `cycle ${campCycle || '—'}`
  const fwdStatLabel = fwdRunning ? 'Running' : 'Stopped'
  const fwdStatDetail = fwdTotal > 0
    ? `${fwdProcessed}/${fwdTotal}${fwdBatchTotal ? ` · B${fwdBatch}/${fwdBatchTotal}` : ''}`
    : `tick ${fwdCycle || '—'}`

  const cardClass = [
    'account-card',
    isActive ? 'account-card--active' : '',
    `account-card--${status}`,
    heavyLimit ? 'account-card--sleep' : '',
    isSubAccount ? 'account-card--subscription' : '',
    loginTab && !info ? 'account-card--login-empty' : '',
  ].filter(Boolean).join(' ')

  const loginSlotTitle = loginTab ? `Connect ${label}` : null
  const isSwitching = switchingAccount === slot

  return (
    <article className={`${cardClass} account-card--dense account-card--v3 account-card--live account-card--live-${liveClass}${compactSetup ? ' account-card--setup-compact' : ''}${loginTab && info ? ' account-card--login-manage' : ''}${isSwitching ? ' account-card--switching' : ''}`}>
      {isSwitching && (
        <div className="account-card-switch-overlay" role="status" aria-live="polite">
          <InlineLoader label={`Loading ${label}…`} size={16} />
        </div>
      )}
      {info ? (
        <>
          <div className="acct-v3-shine" aria-hidden />
          <header className="acct-v3-header">
            <div className="acct-v3-identity">
              <AccountNameEditor
                slot={slot}
                info={info}
                onRenamed={onRenamed}
                startEditing={nameEditOpen}
                onEditingChange={open => { if (!open) setNameEditOpen(false) }}
              />
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
            {compactSetup ? (
              <div className="acct-v3-stats-bar" role="group" aria-label="Account stats">
                {(membership != null || refreshingJoined) && (
                  <span
                    className={`acct-v3-stat${membershipStale ? ' acct-v3-stat--warn' : ''}`}
                    title={membershipTooltip}
                  >
                    <strong>{refreshingJoined ? '…' : membership.total}</strong>
                    <span className="acct-v3-stat-label">groups</span>
                  </span>
                )}
                {joinToday && (
                  <span
                    className={`acct-v3-stat acct-v3-stat--joins${joinsTone === 'bad' ? ' acct-v3-stat--bad' : joinsTone === 'warn' ? ' acct-v3-stat--warn' : ''}`}
                    title={JOINS_TODAY_TOOLTIP}
                  >
                    <strong>{joinToday.today}{joinToday.limit != null ? `/${joinToday.limit}` : ''}</strong>
                    <span className="acct-v3-stat-label">joins today</span>
                  </span>
                )}
                {showCampaignUi && (
                  <span
                    className={`acct-v3-stat acct-v3-stat--desk${campRunning ? ' acct-v3-stat--live' : ''}`}
                    title={`Campaign: ${campSuccess} sent · ${campFailed} failed`}
                  >
                    <strong>Campaign {campStatLabel.toLowerCase()}</strong>
                    <span className="acct-v3-stat-label">{campStatDetail}</span>
                  </span>
                )}
                {showForwardingUi && (
                  <span
                    className={`acct-v3-stat acct-v3-stat--desk${fwdRunning ? ' acct-v3-stat--live' : ''}`}
                    title={`Forward tick #${fwdCycle} · sent ${fwdSuccess} · fail ${fwdFailed}`}
                  >
                    <strong>Forward {fwdStatLabel.toLowerCase()}</strong>
                    <span className="acct-v3-stat-label">{fwdStatDetail}</span>
                  </span>
                )}
                {hasHealth && (
                  <span className={`acct-v3-stat acct-v3-stat--health${healthTone === 'good' ? ' acct-v3-stat--live' : healthTone === 'warning' ? ' acct-v3-stat--warn' : healthTone === 'bad' ? ' acct-v3-stat--bad' : ''}`}>
                    <strong>{healthScore}%</strong>
                    <span className="acct-v3-stat-label">health</span>
                  </span>
                )}
                {membership && !refreshingJoined && (
                  <button
                    type="button"
                    className="acct-v3-stat acct-v3-stat--link"
                    onClick={() => onRefreshJoined(slot)}
                    disabled={refreshingJoined}
                  >
                    Rescan groups
                  </button>
                )}
              </div>
            ) : (
              <>
                <MetricGrid columns={2} className="acct-v3-grid">
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
                  {showCampaignUi && (
                    <MetricBlock
                      className="acct-v3-cell acct-v3-cell--feature"
                      label="Campaign"
                      value={campRunning ? 'Running' : 'Stopped'}
                      sub={campTotal > 0 ? `${campProcessed}/${campTotal} · cycle ${campCycle || '—'}` : `cycle ${campCycle || '—'}`}
                      tone={campRunning ? 'good' : 'neutral'}
                      title={`Campaign: ${campSuccess} sent · ${campFailed} failed`}
                    />
                  )}
                  {showForwardingUi && (
                    <MetricBlock
                      className="acct-v3-cell acct-v3-cell--feature"
                      label="Forwarding"
                      value={fwdRunning ? 'Running' : 'Stopped'}
                      sub={fwdTotal > 0
                        ? `${fwdProcessed}/${fwdTotal}${fwdJoined > fwdTotal ? ` · ${fwdJoined} joined` : ''}${fwdBatchTotal ? ` · B${fwdBatch}/${fwdBatchTotal}` : ''}`
                        : (fwdJoined ? `${fwdJoined} joined` : `tick ${fwdCycle || '—'}`)}
                      tone={fwdRunning ? 'good' : 'neutral'}
                      title={`Forward tick #${fwdCycle} · sent ${fwdSuccess} · skip ${fwdSkipped} · fail ${fwdFailed}`}
                    />
                  )}
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
                    ) : (
                      <>
                        {metaLine}
                        {membership && (
                          <>
                            {' · '}
                            <button
                              type="button"
                              className="acct-v3-meta-link"
                              onClick={() => onRefreshJoined(slot)}
                              disabled={refreshingJoined}
                            >
                              Rescan groups
                            </button>
                          </>
                        )}
                      </>
                    )}
                  </p>
                )}
              </>
            )}
          </div>

          <div className={`acct-v3-setup-flow${workspaceMode ? ` acct-v3-setup-flow--${workspaceMode}` : ''}${compactSetup ? ' acct-v3-setup-flow--compact' : ''}`} onClick={e => e.stopPropagation()}>
            {modeMismatch && (
              <div className="modes-setup-mismatch acct-v3-mode-mismatch">
                <p className="stat-hint">
                  Account is on <strong>{accountMode}</strong> — switch to <strong>{workspaceMode === 'forwarding' ? 'Forward' : 'Campaign'}</strong> to use this workspace.
                </p>
                <AccountModeSwitcher
                  slot={slot}
                  postingModeConfig={postingModeConfig || acctState?.posting_mode_config}
                  postingModes={postingModes}
                  accountStates={accountStates}
                  onUpdated={onPostingModeUpdated}
                  className="acct-v3-mode-switch"
                />
              </div>
            )}
            <div className="acct-v3-toolbar">
              <div className="acct-v3-toolbar-run">
                <AccountPrimaryActions
                  slot={slot}
                  postingModeConfig={postingModeConfig || acctState?.posting_mode_config}
                  postingModes={postingModes}
                  accountStates={accountStates}
                  acctState={acctState}
                  forwardJob={forwardJob}
                  onShutdown={onShutdown}
                  onStart={onStart}
                  onStop={onStop}
                  accountActionLoading={accountActionLoading}
                  forcedMode={workspaceMode || undefined}
                  className="acct-v3-primary-actions"
                />
              </div>
              <div className="acct-v3-toolbar-account" aria-label="Account actions">
                <Button
                  variant="secondary"
                  size="sm"
                  className="acct-v3-btn-action acct-v3-btn-rename"
                  onClick={() => setNameEditOpen(true)}
                >
                  Rename
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  className="acct-v3-btn-action acct-v3-btn-logout"
                  onClick={doLogout}
                  disabled={loading || anyRunning}
                  title={anyRunning ? 'Stop the account before logging out' : undefined}
                >
                  Log out
                </Button>
              </div>
              <Button
                variant="ghost"
                size="sm"
                className="acct-v3-btn-action acct-v3-btn-restart"
                onClick={handleRestart}
                disabled={startLoading || stopLoading || campStartLoading || fwdStartLoading}
              >
                ↻ Restart
              </Button>
            </div>
            <details className="acct-setup-details">
              <summary className="acct-setup-details__summary">
                {workspaceMode === 'forwarding' ? 'Forward message & settings' : workspaceMode === 'campaign' ? 'Campaign message & settings' : 'Message & settings'}
              </summary>
              <PostingModePanel
                slot={slot}
                postingModeConfig={postingModeConfig || acctState?.posting_mode_config}
                postingModes={postingModes}
                accountStates={accountStates}
                acctRunning={anyRunning}
                onUpdated={onPostingModeUpdated}
                onStartForward={s => onStart(s, false, 'forwarding')}
                onStopForward={s => onStop(s, 'forwarding')}
                setupFilter={uiFilter === 'all' ? workspaceMode || 'all' : uiFilter}
                layout="simple"
                primaryMode={primaryMode}
              />
              {showMessageEditor && (
                <div className="acct-v3-message-editor">
                  <MessageEditor
                    slot={slot}
                    customMessage={customMessage}
                    onSaved={onMessageSaved || (() => {})}
                  />
                </div>
              )}
            </details>
          </div>
        </>
      ) : step === 'idle' ? (
        <div className="account-card-login">
          {loginTab && (
            <>
              <h3 className="section-title-sm">{loginSlotTitle}</h3>
              <p className="stat-hint">Enter the Telegram phone number for this slot. You will get one OTP in the Telegram app.</p>
            </>
          )}
          {!loginTab && <p className="stat-hint">Not logged in</p>}
          <button type="button" className="btn btn--success" onClick={() => { resetPhoneFields(); setStep('phone') }}>
            {loginTab ? 'Connect with phone + OTP' : '+ Login'}
          </button>
        </div>
      ) : step === 'phone' ? (
        <div className="account-card-form" onClick={e => e.stopPropagation()}>
          {loginTab && <h3 className="section-title-sm">{loginSlotTitle}</h3>}
          <label className="field-label">Step 1 — Phone number</label>
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
          {loginTab && <h3 className="section-title-sm">{loginSlotTitle}</h3>}
          <p className="field-hint">Step 2 — OTP sent to <strong>{phone}</strong>. Check the Telegram app on that phone.</p>
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
