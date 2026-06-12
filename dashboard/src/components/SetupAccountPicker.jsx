import React from 'react'
import { AccountMiniCard } from './AccountCard.jsx'
import { Button } from './ui/Button.jsx'
import { accountLabel, isSubscriptionAccount } from '../utils/accountUi.js'

/**
 * Account chips for Modes / Groups tabs (Accounts tab has the full grid).
 */
export function SetupAccountPicker({
  slots = [],
  activeSlot,
  accountInfo = {},
  accountStates = {},
  postingModes = {},
  accountShutdown = {},
  subscriptionSlots = [],
  switchingAccount = null,
  onSelect,
  onOpenAccountsTab,
}) {
  if (!slots.length) {
    return (
      <div className="setup-account-picker setup-account-picker--empty">
        <p className="setup-account-picker__empty-title">No accounts logged in</p>
        <p className="stat-hint setup-account-picker__empty-hint">
          Log in with phone + OTP on the Accounts tab first.
        </p>
        {onOpenAccountsTab && (
          <Button type="button" variant="primary" size="sm" onClick={onOpenAccountsTab}>
            Go to Accounts
          </Button>
        )}
      </div>
    )
  }

  return (
    <div className="setup-account-picker">
      <div className="setup-account-picker__head">
        <span className="setup-account-picker__label">Account</span>
        {activeSlot && accountInfo[activeSlot] && (
          <span className="setup-account-picker__active">
            Editing {accountLabel(activeSlot)}
          </span>
        )}
      </div>
      <div className="setup-account-picker__grid" role="tablist" aria-label="Choose account">
        {slots.map(slot => (
          <AccountMiniCard
            key={slot}
            slot={slot}
            selected={activeSlot === slot}
            info={accountInfo[slot]}
            acctState={accountStates[slot]}
            accountShutdown={accountShutdown}
            postingModes={postingModes}
            accountStates={accountStates}
            switchingAccount={switchingAccount}
            isSubscription={isSubscriptionAccount(slot, subscriptionSlots, accountInfo)}
            onSelect={onSelect}
          />
        ))}
      </div>
    </div>
  )
}
