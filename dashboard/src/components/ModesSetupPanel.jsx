import React from 'react'

import { ForwardMessagePanel } from './ForwardMessagePanel.jsx'
import { MessageEditor } from './MessageEditor.jsx'
import { PostingModePanel } from './PostingModePanel.jsx'
import { AccountModeSwitcher } from './AccountModeSwitcher.jsx'
import { AccountPrimaryActions } from './AccountPrimaryActions.jsx'
import { accountPrimaryMode } from '../utils/accountUi.js'
import { WORKSPACE_CAMPAIGN, WORKSPACE_FORWARDING } from '../utils/workspaceMode.js'

/**
 * Modes tab — setup for the active global workspace (Forward or Campaign only).
 */
export function ModesSetupPanel({
  slot,
  workspaceMode = WORKSPACE_FORWARDING,
  customMessage,
  rewriteEnabled,
  cyclePreview,
  onMessageSaved,
  onPostingModeUpdated,
  postingModeConfig,
  postingModes,
  accountStates,
  acctRunning = false,
  forwardJob,
  workerRunning = false,
  loggedIn = false,
  onStartAccount,
  onStopAccount,
  accountActionLoading = null,
}) {
  const fwd = postingModeConfig?.forwarding || {}
  const forwardSourceType = fwd.source_type === 'telegram_post' ? 'telegram_post' : 'template'
  const acctState = slot ? accountStates?.[slot] || {} : {}
  const accountMode = slot ? accountPrimaryMode(accountStates, slot, postingModes) : 'off'
  const modeMismatch = slot && accountMode !== 'off' && accountMode !== workspaceMode

  const showMessageEditor = workspaceMode === WORKSPACE_CAMPAIGN
    || (workspaceMode === WORKSPACE_FORWARDING && forwardSourceType === 'template')

  if (!slot) {
    return (
      <div className="modes-setup-empty">
        <p className="modes-setup-empty__title">Choose an account</p>
        <p className="stat-hint modes-setup-empty__hint">
          Tap a card in the <strong>Account</strong> row above, or open the Accounts tab to log in.
        </p>
      </div>
    )
  }

  return (
    <div className={`modes-setup-panel modes-setup-panel--${workspaceMode}`}>
      {modeMismatch && (
        <div className="modes-setup-mismatch">
          <p className="stat-hint">
            This account is on <strong>{accountMode}</strong> — switch it to match{' '}
            <strong>{workspaceMode === WORKSPACE_FORWARDING ? 'Forward' : 'Campaign'}</strong>.
          </p>
          <AccountModeSwitcher
            slot={slot}
            postingModeConfig={postingModeConfig}
            postingModes={postingModes}
            accountStates={accountStates}
            onUpdated={onPostingModeUpdated}
            className="modes-setup-mode-switch"
          />
        </div>
      )}

      <AccountPrimaryActions
        slot={slot}
        postingModeConfig={postingModeConfig}
        postingModes={postingModes}
        accountStates={accountStates}
        acctState={acctState}
        forwardJob={forwardJob}
        onStart={onStartAccount}
        onStop={onStopAccount}
        accountActionLoading={accountActionLoading}
        forcedMode={workspaceMode}
        className="modes-setup-primary-actions"
      />

      <details className="acct-setup-details modes-setup-details" open>
        <summary className="acct-setup-details__summary">
          {workspaceMode === WORKSPACE_FORWARDING ? 'Forward message & settings' : 'Campaign message & settings'}
        </summary>
        <PostingModePanel
          slot={slot}
          postingModeConfig={postingModeConfig}
          postingModes={postingModes}
          accountStates={accountStates}
          acctRunning={acctRunning}
          onUpdated={onPostingModeUpdated}
          onStartForward={s => onStartAccount?.(s, false, 'forwarding')}
          onStopForward={s => onStopAccount?.(s, 'forwarding')}
          setupFilter={workspaceMode}
          layout="simple"
          primaryMode={workspaceMode}
        />

        {showMessageEditor && (
          <MessageEditor
            key={`${slot}-${workspaceMode}-template`}
            slot={slot}
            customMessage={customMessage}
            rewriteEnabled={rewriteEnabled}
            cyclePreview={cyclePreview}
            onSaved={onMessageSaved}
          />
        )}

        {workspaceMode === WORKSPACE_FORWARDING && fwd.forward_dispatch === 'manual' && (
          <ForwardMessagePanel
            slot={slot}
            job={forwardJob}
            workerRunning={workerRunning}
            loggedIn={loggedIn}
            postingModeConfig={postingModeConfig}
          />
        )}

        {workspaceMode === WORKSPACE_FORWARDING && forwardSourceType === 'telegram_post' && (
          <p className="stat-hint modes-setup-hint">
            This account forwards from the <strong>t.me link</strong> above — not the template box.
          </p>
        )}
      </details>
    </div>
  )
}
