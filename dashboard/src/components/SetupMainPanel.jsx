import React from 'react'
import { AccountFleetGrid } from './AccountFleetGrid.jsx'
import { ModesSetupPanel } from './ModesSetupPanel.jsx'
import { WORKSPACE_CAMPAIGN, WORKSPACE_FORWARDING } from '../utils/workspaceMode.js'
import { aggregateFleetStats } from '../utils/globalStats.js'
import { getDashboardModeFilter } from '../utils/workspaceDashboard.js'

/**
 * Setup tab — account grid + per-account mode/message configuration.
 */
export function SetupMainPanel({
  slots,
  accountFilter = WORKSPACE_FORWARDING,
  onAccountFilterChange,
  onModeApplied,
  activeSlot,
  accountInfo,
  accountStates,
  postingModes,
  accountShutdown,
  subscriptionSlots = [],
  switchingAccount,
  onSelectAccount,
  onOpenLoginTab,
  onPostingModeUpdated,
  modesProps,
}) {
  const modeFilter = getDashboardModeFilter(accountFilter)
  const fleet = aggregateFleetStats(
    { account_states: accountStates, account_info: accountInfo, account_shutdown: accountShutdown },
    slots,
    { postingModes, modeFilter },
  )

  return (
    <div className="setup-main-panel">
      <AccountFleetGrid
        perAccount={fleet.perAccount}
        accountInfo={accountInfo}
        accountStates={accountStates}
        subscriptionSlots={subscriptionSlots}
        activeAccount={activeSlot}
        onSelectAccount={onSelectAccount}
        switchingAccount={switchingAccount}
      />
      <ModesSetupPanel
        slot={activeSlot}
        workspaceMode={accountFilter === WORKSPACE_CAMPAIGN ? WORKSPACE_CAMPAIGN : WORKSPACE_FORWARDING}
        customMessage={modesProps?.customMessage}
        rewriteEnabled={modesProps?.rewriteEnabled}
        cyclePreview={modesProps?.cyclePreview}
        onMessageSaved={modesProps?.onMessageSaved ?? onPostingModeUpdated}
        onPostingModeUpdated={onPostingModeUpdated ?? modesProps?.onPostingModeUpdated}
        postingModeConfig={modesProps?.postingModeConfig ?? accountStates?.[activeSlot]?.posting_mode_config}
        postingModes={postingModes}
        accountStates={accountStates}
        acctRunning={modesProps?.acctRunning}
        forwardJob={modesProps?.forwardJob}
        workerRunning={modesProps?.workerRunning}
        loggedIn={modesProps?.loggedIn ?? !!accountInfo?.[activeSlot]}
        onStartAccount={modesProps?.onStartAccount}
        onStopAccount={modesProps?.onStopAccount}
        accountActionLoading={modesProps?.accountActionLoading}
      />
      {!slots?.length && (
        <p className="stat-hint setup-main-panel__hint">
          No logged-in accounts yet.{' '}
          <button type="button" className="linkish-btn" onClick={onOpenLoginTab}>
            Open login tab
          </button>
        </p>
      )}
    </div>
  )
}
