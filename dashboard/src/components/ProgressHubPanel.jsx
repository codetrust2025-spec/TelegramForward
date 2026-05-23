import React, { useMemo, useState } from 'react'
import { ButtonContent } from '../Loader.jsx'
import { DailyStatsPanel } from './DailyStatsPanel.jsx'
import { ProgressStatsPanel, ProgressStatChip } from './ProgressStatsPanel.jsx'
import { AccountFleetGrid } from './AccountFleetGrid.jsx'
import { FleetHealthPanel } from './FleetHealthPanel.jsx'
import { AccountPerformanceChart } from './AccountPerformanceChart.jsx'
import { ProgressSection } from './ProgressSection.jsx'
import { ProgressBar } from './ui/ProgressBar.jsx'
import { accountLabel, formatCountdown } from '../utils/accountUi'
import { buildFleetHealthRows, sortFleetHealthRows } from '../utils/fleetHealth.js'
import { SegmentedControl } from './ui/SegmentedControl.jsx'

const SECTIONS = [
  { id: 'overview', label: 'Overview' },
  { id: 'fleet', label: 'Fleet' },
  { id: 'performance', label: 'Performance' },
  { id: 'accounts', label: 'Accounts' },
  { id: 'selected', label: 'Selected' },
]

function ProgressHubPin({ fleet, globalCountdown, alertCount, activeAccountLabel }) {
  const {
    runningCount,
    sleepingCount,
    sending,
    hasAnyCycle,
    progressValue,
    progressMax,
  } = fleet

  let statusLabel = 'Idle'
  if (sending.length > 0) {
    statusLabel = sending.length === 1 ? 'Sending' : `${sending.length} sending`
  } else if (runningCount > 0) {
    statusLabel = globalCountdown > 0 ? 'Waiting' : 'Running'
  } else if (sleepingCount > 0) {
    statusLabel = 'Sleeping'
  }

  const activeCount = runningCount + sleepingCount

  return (
    <div className="progress-hub-pin" role="status" aria-live="polite">
      <span className={`progress-hub-pin-status progress-hub-pin-status--${statusLabel.toLowerCase().replace(/\s+/g, '_')}`}>
        {statusLabel}
      </span>
      {globalCountdown > 0 && activeCount > 0 && (
        <span className="progress-hub-pin-countdown">{formatCountdown(globalCountdown)}</span>
      )}
      <span className="progress-hub-pin-stat" title="Accounts running or paused">
        <strong>{activeCount}</strong> active
      </span>
      <span className="progress-hub-pin-stat" title="Fleet cycle progress">
        <strong>{hasAnyCycle ? progressValue : 0}/{progressMax}</strong> groups
      </span>
      {alertCount > 0 && (
        <span className="progress-hub-pin-alert" title="Accounts needing attention">
          {alertCount} alert{alertCount !== 1 ? 's' : ''}
        </span>
      )}
      {activeAccountLabel && (
        <span className="progress-hub-pin-account">{activeAccountLabel}</span>
      )}
    </div>
  )
}

export function ProgressHubPanel({
  fleet,
  globalCountdown,
  sentWindowLabel,
  accountInfo,
  subscriptionSlots,
  dailyStats,
  accountSlots,
  onDailyStatsUpdate,
  onConfirmReset,
  activeAccount,
  activeAcctState,
  accountStates,
  onSelectAccount,
  switchingAccount,
  accountProgress,
  cycle,
  tools,
}) {
  const [section, setSection] = useState('overview')
  const [layout, setLayout] = useState('single')

  const subs = subscriptionSlots?.length ? subscriptionSlots : []
  const activeAccountLabel = activeAccount ? accountLabel(activeAccount) : null

  const alertCount = useMemo(() => {
    const resetTs = dailyStats?.reset_timestamp ?? 0
    const rows = sortFleetHealthRows(
      buildFleetHealthRows(
        fleet.perAccount,
        accountInfo,
        dailyStats?.window,
        resetTs,
      ),
    )
    return rows.filter(r => r.attention).length
  }, [fleet.perAccount, accountInfo, dailyStats?.window, dailyStats?.reset_timestamp])

  const fleetChipsSecondary = (
    <>
      <ProgressStatChip label="Still to post" value={fleet.needResend} title="Groups still waiting across all accounts" />
      <ProgressStatChip label="Skipped (already posted)" value={fleet.skippedAlreadyPosted} warn title="Skipped — all accounts" />
      {fleet.skippedCooldown + fleet.skippedOther > 0 && (
        <ProgressStatChip
          label="Paused to avoid spam"
          value={fleet.skippedCooldown + fleet.skippedOther}
          warn
          icon="⏳"
          helper="Temporary safety delay"
          title="Groups temporarily paused due to safe messaging delay. They are delayed, not failed."
        />
      )}
      <ProgressStatChip
        label={`Sent (${sentWindowLabel.toLowerCase()})`}
        value={fleet.messagesSent24h}
        title={`Forwards — ${sentWindowLabel.toLowerCase()} — all accounts`}
      />
    </>
  )

  function renderOverview() {
    return (
      <div className="progress-hub-section">
        <DailyStatsPanel
          dailyStats={dailyStats}
          accountSlots={accountSlots}
          accountInfo={accountInfo}
          accountStates={accountStates}
          onConfirmReset={onConfirmReset}
          onDailyStatsUpdate={onDailyStatsUpdate}
        />
        <ProgressStatsPanel
          title="Fleet cycle summary"
          subtitle="Primary metrics — all accounts combined"
          helpText="These totals appear only here. Other tabs show health, ranking, or per-account detail."
          totalGroups={fleet.masterTotal || 0}
          success={fleet.success}
          failed={fleet.failed}
          successRate={fleet.successRate}
          processed={fleet.processed}
          secondary={fleetChipsSecondary}
        >
          <ProgressBar
            value={fleet.hasAnyCycle ? fleet.progressValue : 0}
            max={fleet.progressMax}
            label={`Fleet progress: ${fleet.hasAnyCycle ? fleet.progressValue : 0} of ${fleet.progressMax} groups processed this cycle`}
            tone="success"
            large
            className="fleet-progress-bar"
          />
        </ProgressStatsPanel>
      </div>
    )
  }

  function renderFleet() {
    return (
      <div className="progress-hub-section progress-hub-section--scroll">
        {fleet.perAccount.length > 0 ? (
          <FleetHealthPanel
            perAccount={fleet.perAccount}
            accountInfo={accountInfo}
            statsWindow={dailyStats?.window}
            dailyStats={dailyStats}
          />
        ) : (
          <p className="stat-hint">No logged-in accounts to show fleet health.</p>
        )}
      </div>
    )
  }

  function renderPerformance() {
    return (
      <div className="progress-hub-section progress-hub-section--scroll">
        {fleet.perAccount.length > 0 ? (
          <AccountPerformanceChart
            perAccount={fleet.perAccount}
            accountInfo={accountInfo}
            statsWindow={dailyStats?.window}
            subscriptionSlots={subs}
            rankingOnly
          />
        ) : (
          <p className="stat-hint">No performance data yet.</p>
        )}
      </div>
    )
  }

  function renderAccounts() {
    return (
      <div className="progress-hub-section progress-hub-section--scroll">
        <AccountFleetGrid
          perAccount={fleet.perAccount}
          accountInfo={accountInfo}
          accountStates={accountStates}
          subscriptionSlots={subs}
          activeAccount={activeAccount}
          onSelectAccount={onSelectAccount}
          switchingAccount={switchingAccount}
          onAccountSelected={() => setSection('selected')}
        />
      </div>
    )
  }

  function renderSelected() {
    const {
      displaySuccess,
      displayFailed,
      displayActiveGroups,
      displaySkippedPosted,
      displaySkippedCooldown,
      displaySkippedOther,
      displaySent24h,
    } = accountProgress

    return (
      <div className="progress-hub-section progress-hub-section--scroll">
        <ProgressStatsPanel
          title={activeAccountLabel ? activeAccountLabel : 'Selected account'}
          subtitle="Cycle deep dive — fleet status is in the top bar"
          hideGrid
          secondary={(
            <>
              <ProgressStatChip label="Posted OK" value={displaySuccess} title="Sent this cycle — this account only" />
              <ProgressStatChip label="Failed" value={displayFailed} title="Failed this cycle — this account only" />
              <ProgressStatChip label="Still to post" value={displayActiveGroups} title="Groups waiting this cycle" />
              <ProgressStatChip label="Already in chat" value={displaySkippedPosted} warn title="Skipped — already posted" />
              {displaySkippedCooldown + displaySkippedOther > 0 && (
                <ProgressStatChip
                  label="Paused to avoid spam"
                  value={displaySkippedCooldown + displaySkippedOther}
                  warn
                  icon="⏳"
                  helper="Temporary safety delay"
                  title="Groups temporarily paused due to safe messaging delay. They are delayed, not failed."
                />
              )}
              <ProgressStatChip
                label={`Sent (${sentWindowLabel.toLowerCase()})`}
                value={displaySent24h}
                title={`Forwards — ${sentWindowLabel.toLowerCase()} — this account`}
              />
            </>
          )}
        >
          <ProgressSection
            activeAcctState={activeAcctState}
            displayCurrentGroup={cycle.displayCurrentGroup}
            countdown={cycle.countdown}
            cycleElapsed={cycle.cycleElapsed}
            progressValue={cycle.progressValue}
            progressMax={cycle.progressMax}
            hasCycleRun={cycle.hasCycleRun}
            deepDive
          />
        </ProgressStatsPanel>

        <div className="controls-row controls-panel controls-panel--account">
          <div className="action-group">
            <button type="button" className="btn btn--accent btn--sm" onClick={tools.openGroups} disabled={tools.loadingGroups}>
              <ButtonContent loading={tools.loadingGroups} loadingLabel="Loading…">
                View groups
              </ButtonContent>
            </button>
            <button
              type="button"
              className="btn btn--danger btn--sm"
              onClick={() => tools.exportGroupLists('dead')}
              disabled={!!tools.exportingKind}
            >
              <ButtonContent loading={tools.exportingKind === 'dead'} loadingLabel="…">Dead list</ButtonContent>
            </button>
            <button
              type="button"
              className="btn btn--success btn--sm"
              onClick={() => tools.exportGroupLists('good')}
              disabled={!!tools.exportingKind}
            >
              <ButtonContent loading={tools.exportingKind === 'good'} loadingLabel="…">Active list</ButtonContent>
            </button>
            <button type="button" className="btn btn--ghost btn--sm" onClick={tools.onResetStats}>
              Reset stats
            </button>
          </div>
        </div>
      </div>
    )
  }

  const sectionRenderers = {
    overview: renderOverview,
    fleet: renderFleet,
    performance: renderPerformance,
    accounts: renderAccounts,
    selected: renderSelected,
  }

  return (
    <div className="progress-hub">
      <ProgressHubPin
        fleet={fleet}
        globalCountdown={globalCountdown}
        alertCount={alertCount}
        activeAccountLabel={activeAccountLabel}
      />

      <div className="progress-hub-nav">
        <SegmentedControl
          className="progress-hub-tabs"
          label="Progress sections"
          role="tablist"
          options={SECTIONS.map(s => ({
            value: s.id,
            label: s.label,
            role: 'tab',
            controls: `progress-hub-panel-${s.id}`,
          }))}
          value={section}
          onChange={(next) => {
            setLayout('single')
            setSection(next)
          }}
        />
        <SegmentedControl
          className="progress-hub-layout-toggle"
          label="Layout mode"
          options={[
            { value: 'single', label: 'Single' },
            { value: 'split', label: 'Split' },
          ]}
          value={layout}
          onChange={setLayout}
        />
      </div>

      <div className={`progress-hub-body progress-hub-body--${layout}`}>
        {layout === 'single' ? (
          <div
            id={`progress-hub-panel-${section}`}
            className="progress-hub-pane"
            role="tabpanel"
            aria-label={`${SECTIONS.find(s => s.id === section)?.label || 'Overview'} panel`}
          >
            {(sectionRenderers[section] || renderOverview)()}
          </div>
        ) : (
          <>
            <div className="progress-hub-pane progress-hub-pane--split" aria-label="Fleet health">
              <h4 className="progress-hub-split-title">Fleet health</h4>
              {renderFleet()}
            </div>
            <div className="progress-hub-pane progress-hub-pane--split" aria-label="Top performers">
              <h4 className="progress-hub-split-title">Top performers</h4>
              {renderPerformance()}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
