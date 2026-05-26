import React, { useMemo } from 'react'
import { AccountCard, AccountMiniCard } from './AccountCard.jsx'
import {
  accountLabel,
  getAccountSlots,
  getLoggedInSlots,
  getNextAvailableSlot,
  isAccountLoggedIn,
  isSubscriptionAccount,
  sortAccountsForDisplay,
} from '../utils/accountUi'

export function AccountPanel({
  state,
  configuredSlots,
  subscriptionSlots = [],
  onAccountChange,
  onStartAccount,
  onStopAccount,
  onSwitchAccount,
  onRefreshJoined,
  refreshingJoinedSlot,
  accountActionLoading,
  switchingAccount,
  onMessageSaved,
}) {
  const accountInfo = state.account_info || {}
  const allSlots = getAccountSlots(state, configuredSlots)
  const subs = Array.isArray(subscriptionSlots) ? subscriptionSlots : []

  const loggedInSlots = useMemo(
    () => sortAccountsForDisplay(
      getLoggedInSlots(allSlots, accountInfo),
      state.account_states,
      accountInfo,
    ),
    [allSlots, accountInfo, state.account_states],
  )

  const nextAvailable = useMemo(
    () => getNextAvailableSlot(allSlots, accountInfo),
    [allSlots, accountInfo],
  )

  const visibleActive = useMemo(() => {
    const active = state.active_account
    if (active && isAccountLoggedIn(accountInfo, active)) {
      return active
    }
    if (active && allSlots.includes(active) && !isAccountLoggedIn(accountInfo, active)) {
      return active
    }
    return loggedInSlots[0] ?? nextAvailable ?? null
  }, [state.active_account, accountInfo, allSlots, loggedInSlots, nextAvailable])

  const sectionSub = loggedInSlots.length === 0
    ? 'No accounts logged in'
    : `${loggedInSlots.length} account${loggedInSlots.length !== 1 ? 's' : ''}`

  return (
    <section className="accounts-section">
      <header className="section-header section-header--compact">
        <h2 className="section-title">Accounts</h2>
        <span className="section-sub">{sectionSub}</span>
      </header>

      <div className="accounts-grid" role="tablist" aria-label="Account selector">
        {loggedInSlots.map(slot => (
          <AccountMiniCard
            key={slot}
            slot={slot}
            selected={visibleActive === slot}
            info={accountInfo[slot]}
            acctState={state.account_states?.[slot]}
            accountStatus={state.account_status?.[slot]}
            switching={switchingAccount != null}
            isSubscription={isSubscriptionAccount(slot, subs, accountInfo)}
            onSelect={onSwitchAccount}
          />
        ))}
        {nextAvailable && (
          <button
            type="button"
            className={`account-mini account-mini--add${visibleActive === nextAvailable ? ' account-mini--selected' : ''}`}
            onClick={() => onSwitchAccount(nextAvailable)}
            disabled={switchingAccount != null}
            aria-label="Add account — log in to a new slot"
          >
            <span className="account-mini-add-icon">+</span>
            <span className="account-mini-add-label">Add account</span>
          </button>
        )}
      </div>

      {visibleActive && (
        <AccountCard
          key={visibleActive}
          slot={visibleActive}
          label={accountLabel(visibleActive)}
          info={accountInfo[visibleActive]}
          isActive
          isSubscription={isSubscriptionAccount(visibleActive, subs, accountInfo)}
          acctRunning={!!state.account_states?.[visibleActive]?.running}
          onLogin={onAccountChange}
          onLogout={onAccountChange}
          onStart={onStartAccount}
          onStop={onStopAccount}
          onRefreshJoined={onRefreshJoined}
          refreshingJoined={refreshingJoinedSlot === visibleActive}
          accountActionLoading={accountActionLoading}
          acctState={state.account_states?.[visibleActive]}
          accountStatus={state.account_status?.[visibleActive]}
          statsWindow={state.daily_stats?.window}
          sentInWindow={state.daily_stats?.per_account?.[visibleActive]?.forwarded}
          customMessage={state.account_messages?.[visibleActive] ?? state.custom_message ?? ''}
          onMessageSaved={onMessageSaved}
        />
      )}
    </section>
  )
}
