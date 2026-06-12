import React, { useMemo } from 'react'
import { getDashboardModeConfig } from '../utils/workspaceDashboard.js'
import { accountRowsForDashboard, buildDeskDashSummary } from '../dashboard/dashboardStats.js'
import { buildFleetHealthRows, dailyStatsCutoff } from '../utils/fleetHealth.js'
import { formatCountdown } from '../utils/accountUi.js'
import {
  DeskDonut,
  DeskPerformanceChart,
  DeskKpiBar,
  buildRecentActivity,
  buildDeskAlerts,
} from './deskDashboardWidgets.jsx'

export function DesktopDashboardHome({
  state,
  loggedInSlots,
  postingModes,
  inboxUnreadTotal,
  fleet,
  globalCountdown,
  sentWindowLabel,
  activeSlot,
  activeRunning,
  anyProcessRunning = false,
  onSelectAccount,
  onOpenSetup,
  onOpenProgress,
  onResetReach,
  onStartAccount,
  onStopAccount,
  accountActionLoading,
  shutdownListCount,
  onNavBulk,
  onNavShutdown,
  onNavLogs,
  onNavData,
  tickOverview,
  recentLogs,
  workspaceMode,
}) {
  const mode = getDashboardModeConfig(workspaceMode)

  const summary = useMemo(
    () =>
      buildDeskDashSummary({
        state,
        loggedInSlots,
        postingModes,
        inboxUnreadTotal,
        fleet,
        modeFilter: mode.modeFilter,
      }),
    [state, loggedInSlots, postingModes, inboxUnreadTotal, fleet, mode.modeFilter],
  )

  const accountRows = useMemo(
    () => accountRowsForDashboard(state, loggedInSlots, postingModes, mode.modeFilter),
    [state, loggedInSlots, postingModes, mode.modeFilter],
  )

  const healthRows = useMemo(() => {
    const resetTs = state.daily_stats?.reset_timestamp ?? 0
    const cutoffTs = dailyStatsCutoff(state.daily_stats)
    return buildFleetHealthRows(
      fleet.perAccount || [],
      state.account_info,
      state.daily_stats?.window,
      resetTs,
      { postingModes, accountStates: state.account_states, cutoffTimestamp: cutoffTs },
    )
  }, [fleet.perAccount, state.account_info, state.daily_stats, postingModes, state.account_states])

  const activity = useMemo(
    () => buildRecentActivity(recentLogs, state.account_info, 10),
    [recentLogs, state.account_info],
  )

  const alerts = useMemo(
    () =>
      buildDeskAlerts({
        healthRows,
        failedCount: fleet.failed ?? 0,
        alertCount: summary.alertCount,
      }),
    [healthRows, fleet.failed, summary.alertCount],
  )

  const tick = tickOverview || {}
  const groups = tick.groups ?? summary.progressMax
  const sent = tick.sent ?? summary.tickSent
  const failed = tick.failed ?? fleet.failed ?? 0
  const successRate = tick.successRate ?? summary.successRate
  const remaining = tick.remaining ?? Math.max(0, groups - (summary.progressValue || 0))
  const skipped = tick.skipped ?? fleet.skippedAlreadyPosted ?? 0
  const progressPct = summary.progressMax > 0
    ? Math.round((summary.progressValue / summary.progressMax) * 100)
    : 0

  const postsToday = summary.postsToday ?? summary.messagesSent24h ?? 0
  const accountsTotal = mode.isFleet ? summary.totalAccounts : summary.modeEnabledCount
  const runningNow = mode.isCampaign ? summary.campRunning : summary.fwdRunning
  const busy =
    anyProcessRunning
    || accountRows.some(row => row.running)
    || summary.sleeping
    || (Number(fleet?.runningCount) || 0) > 0
    || (Number(fleet?.sleepingCount) || 0) > 0

  function highlight(kind) {
    return mode.highlightKpi === kind ? ' desk-kpi-card--highlight' : ''
  }

  return (
    <div
      className={`desk-dash desk-dash--sigma${mode.isCampaign ? ' desk-dash--campaign' : ''}${mode.isForwarding ? ' desk-dash--forwarding' : ''}`}
    >
      <div className="desk-kpi-row">
        <div className={`desk-kpi-card${highlight('accounts')}`}>
          <div className="desk-kpi-card__head">
            <span className="desk-kpi-card__icon" aria-hidden>👥</span>
            <span className="desk-kpi-card__label">Accounts</span>
          </div>
          <div className="desk-kpi-card__value desk-kpi-card__value--green">{accountsTotal}</div>
          <div className="desk-kpi-card__sub">
            {summary.displayRunning} running · {summary.displayResting} resting
          </div>
          <DeskKpiBar color="#22c55e" />
        </div>

        <div className={`desk-kpi-card${highlight('forward')}`}>
          <div className="desk-kpi-card__head">
            <span className="desk-kpi-card__icon" aria-hidden>{mode.isCampaign ? '📣' : '✈'}</span>
            <span className="desk-kpi-card__label">{mode.postsKpiLabel}</span>
          </div>
          <div className="desk-kpi-card__value desk-kpi-card__value--blue">{postsToday}</div>
          <div className="desk-kpi-card__sub">{(sentWindowLabel || 'since reset').toLowerCase()}</div>
          <DeskKpiBar color={mode.isCampaign ? '#f97316' : '#3b82f6'} />
        </div>

        <div className="desk-kpi-card">
          <div className="desk-kpi-card__head">
            <span className="desk-kpi-card__icon" aria-hidden>✉</span>
            <span className="desk-kpi-card__label">Inbox messages</span>
          </div>
          <div className="desk-kpi-card__value desk-kpi-card__value--purple">{summary.inboxNew}</div>
          <div className="desk-kpi-card__sub">
            {inboxUnreadTotal > 0 ? `${inboxUnreadTotal} unread` : 'New messages'}
          </div>
          <DeskKpiBar color="#8b5cf6" variant="bars" />
        </div>

        <div className={`desk-kpi-card${highlight('campaign')}`}>
          <div className="desk-kpi-card__head">
            <span className="desk-kpi-card__icon" aria-hidden>📣</span>
            <span className="desk-kpi-card__label">
              {mode.isCampaign ? 'Active campaigns' : 'Campaigns'}
            </span>
          </div>
          <div className="desk-kpi-card__value desk-kpi-card__value--orange">{summary.campRunning}</div>
          <div className="desk-kpi-card__sub">
            {mode.isCampaign ? 'accounts posting' : 'running'}
          </div>
          <DeskKpiBar color="#f97316" variant="flat" />
        </div>

        <div className="desk-kpi-card">
          <div className="desk-kpi-card__head">
            <span className="desk-kpi-card__icon" aria-hidden>✓</span>
            <span className="desk-kpi-card__label">Success rate</span>
          </div>
          <div className="desk-kpi-card__value desk-kpi-card__value--teal">{successRate}%</div>
          <div className="desk-kpi-card__sub">this tick</div>
          <DeskKpiBar color="#14b8a6" />
        </div>

        <div className="desk-kpi-card desk-kpi-card--alert">
          <div className="desk-kpi-card__head">
            <span className="desk-kpi-card__icon" aria-hidden>⚠</span>
            <span className="desk-kpi-card__label">Alerts</span>
          </div>
          <div className="desk-kpi-card__value desk-kpi-card__value--red">{summary.alertCount}</div>
          <div className="desk-kpi-card__sub">Requires attention</div>
        </div>
      </div>

      <div className="desk-main-grid">
        <div className="desk-panel desk-panel--tall">
          <div className="desk-panel__head">
            <h2 className="desk-panel__title">{mode.performanceTitle}</h2>
            <span className="desk-panel__meta">{sentWindowLabel || 'Last 24 hours'}</span>
          </div>
          <DeskPerformanceChart
            dailyStats={state.daily_stats}
            logs={recentLogs}
            modeFilter={mode.modeFilter}
            statsWindowLabel={sentWindowLabel || 'Last 24 hours'}
          />
          {summary.sleeping && (
            <p className="desk-panel__hint">
              ⏱ Fleet sleeping {formatCountdown(globalCountdown || summary.countdown)}
            </p>
          )}
        </div>

        <div className="desk-panel desk-panel--tall">
          <div className="desk-panel__head">
            <h2 className="desk-panel__title">Live activity</h2>
            <button type="button" className="desk-panel__link" onClick={onNavLogs}>
              View logs
            </button>
          </div>
          <ul className="desk-activity-list">
            {activity.length === 0 && (
              <li className="desk-activity-item desk-activity-item--empty">No recent activity yet</li>
            )}
            {activity.map(item => (
              <li key={item.id} className="desk-activity-item">
                <span className="desk-activity-item__icon" aria-hidden>{item.icon}</span>
                <span className="desk-activity-item__body">
                  <span className="desk-activity-item__title">{item.title}</span>
                  <span className="desk-activity-item__meta">
                    {item.meta} · {item.ago}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </div>

        <div className="desk-panel desk-panel--tall">
          <div className="desk-panel__head">
            <h2 className="desk-panel__title">
              {mode.isCampaign ? 'Campaign accounts' : mode.isForwarding ? 'Forwarding accounts' : 'Accounts'}
            </h2>
            <button type="button" className="desk-panel__link" onClick={onOpenSetup}>
              Manage
            </button>
          </div>
          {accountRows.length === 0 && (
            <p className="desk-panel__hint">
              No accounts have {mode.isCampaign ? 'campaign' : 'forwarding'} enabled. Open Manage to configure.
            </p>
          )}
          <div className="desk-accounts-scroll">
            {accountRows.map(row => (
              <button
                key={row.slot}
                type="button"
                className="desk-account-row"
                onClick={() => onSelectAccount?.(row.slot)}
              >
                <span
                  className={`mob-account-row__dot mob-account-row__dot--${row.running ? 'on' : 'off'}`}
                  aria-hidden
                />
                <span className="mob-account-row__avatar" style={{ background: row.color }} aria-hidden>
                  {row.initials}
                </span>
                <span className="mob-account-row__info">
                  <div className="mob-account-row__name">{row.displayName}</div>
                  <div className="mob-account-row__sub">{row.subLabel}</div>
                </span>
                <span className={`mob-status-pill mob-status-pill--${row.pillClass}`}>{row.pillLabel}</span>
                <span className="mob-account-row__chev" aria-hidden>›</span>
              </button>
            ))}
          </div>
          <div className="mob-accounts-footer">
            <span>
              {accountsTotal} in {mode.isCampaign ? 'campaign' : mode.isForwarding ? 'forwarding' : 'fleet'}
            </span>
            <span className="mob-accounts-footer__run">{summary.displayRunning} Running</span>
            <span className="mob-accounts-footer__rest">{summary.displayResting} Resting</span>
          </div>
        </div>
      </div>

      <div className="desk-bottom-grid">
        <div className="desk-panel">
          <div className="desk-panel__head">
            <h2 className="desk-panel__title">{mode.overviewTitle}</h2>
            <button type="button" className="desk-panel__link" onClick={onOpenProgress}>
              View all
            </button>
          </div>
          <div className="desk-donut-row">
            <DeskDonut value={groups} max={groups || 1} color="#60a5fa" label="Groups this tick" />
            <DeskDonut value={sent} max={groups || 1} color="#22c55e" label="Sent this tick" />
            <DeskDonut value={failed} max={Math.max(groups, failed, 1)} color="#ef4444" label="Failed" />
            <DeskDonut value={Number(successRate) || 0} max={100} color="#14b8a6" label="Success rate" sublabel="%" />
            <DeskDonut value={remaining} max={groups || 1} color="#8b5cf6" label="Remaining" />
            <DeskDonut value={skipped} max={Math.max(groups, skipped, 1)} color="#f97316" label="Skipped" />
          </div>
          <div className="mob-progress-bar desk-tick-bar" aria-hidden>
            <div className="mob-progress-bar__fill" style={{ width: `${Math.min(100, progressPct)}%` }} />
          </div>
          <p className="desk-tick-foot">
            {mode.tickFootLabel}: <strong>{summary.progressValue}</strong> /{' '}
            <strong>{summary.progressMax}</strong> groups
            <span className="desk-tick-foot__pct">{progressPct}%</span>
          </p>

          <div className="desk-panel__head desk-panel__head--reach">
            <h3 className="desk-panel__subtitle">{mode.reachTitle}</h3>
            <button
              type="button"
              className="btn btn--warn btn--sm desk-reset-reach-btn"
              onClick={onResetReach}
              title="Clear today's counters from now until midnight IST (accounts and logs are kept)"
            >
              ↻ Reset today
            </button>
          </div>
          <div className="desk-reach-metrics desk-reach-metrics--compact">
            <div>
              <div className="desk-overview__stat-label">{mode.postsTodayLabel}</div>
              <div className="desk-overview__stat-value" style={{ color: '#4ade80' }}>{postsToday}</div>
            </div>
            <div>
              <div className="desk-overview__stat-label">{mode.runningNowLabel}</div>
              <div className="desk-overview__stat-value" style={{ color: '#60a5fa' }}>{runningNow}</div>
            </div>
            <div>
              <div className="desk-overview__stat-label">Current sent</div>
              <div className="desk-overview__stat-value" style={{ color: '#fbbf24' }}>{sent}</div>
            </div>
            <div>
              <div className="desk-overview__stat-label">Success rate</div>
              <div className="desk-overview__stat-value" style={{ color: '#a78bfa' }}>{successRate}%</div>
            </div>
          </div>
        </div>

        <div className="desk-panel">
          <h2 className="desk-panel__title">Quick actions</h2>
          <div className="desk-quick-sigma">
            {busy ? (
              <button
                type="button"
                className="desk-quick-btn desk-quick-btn--stop desk-quick-btn--lg"
                disabled={!activeSlot || !!accountActionLoading}
                onClick={() => onStopAccount?.(activeSlot, mode.feature)}
              >
                {mode.stopLabel}
              </button>
            ) : (
              <button
                type="button"
                className="desk-quick-btn desk-quick-btn--start desk-quick-btn--lg"
                disabled={!activeSlot || !!accountActionLoading}
                onClick={() => onStartAccount?.(activeSlot, false, mode.feature)}
              >
                {mode.startLabel}
              </button>
            )}
            <div className="desk-util-grid">
              <button type="button" className="desk-quick-btn desk-quick-btn--util" onClick={onNavBulk}>
                <span className="desk-quick-btn__ico" aria-hidden>☰</span>
                {mode.bulkLabel}
              </button>
              <button type="button" className="desk-quick-btn desk-quick-btn--util" onClick={onNavShutdown}>
                <span className="desk-quick-btn__ico desk-quick-btn__ico--red" aria-hidden>⏻</span>
                Shutdown{shutdownListCount > 0 ? ` (${shutdownListCount})` : ''}
              </button>
              <button type="button" className="desk-quick-btn desk-quick-btn--util" onClick={onNavLogs}>
                <span className="desk-quick-btn__ico desk-quick-btn__ico--purple" aria-hidden>📋</span>
                Logs
              </button>
              <button type="button" className="desk-quick-btn desk-quick-btn--util" onClick={onNavData}>
                <span className="desk-quick-btn__ico desk-quick-btn__ico--blue" aria-hidden>📊</span>
                Data
              </button>
            </div>
          </div>
        </div>

        <div className="desk-panel">
          <div className="desk-panel__head">
            <h2 className="desk-panel__title">Alerts & notifications</h2>
            {summary.alertCount > 0 && (
              <span className="desk-panel__badge">{summary.alertCount}</span>
            )}
          </div>
          <ul className="desk-alerts-list">
            {alerts.length === 0 && (
              <li className="desk-alert-item desk-alert-item--ok">
                <span className="desk-alert-item__icon" aria-hidden>✓</span>
                <span className="desk-alert-item__body">
                  <span className="desk-alert-item__title">All systems operational</span>
                  <span className="desk-alert-item__meta">No alerts right now</span>
                </span>
              </li>
            )}
            {alerts.map(item => (
              <li key={item.id} className={`desk-alert-item desk-alert-item--${item.type}`}>
                <span className="desk-alert-item__icon" aria-hidden>
                  {item.type === 'error' ? '⚠' : item.type === 'warn' ? '!' : 'ℹ'}
                </span>
                <span className="desk-alert-item__body">
                  <span className="desk-alert-item__title">{item.title}</span>
                  <span className="desk-alert-item__meta">
                    {item.meta} · {item.ago}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}
