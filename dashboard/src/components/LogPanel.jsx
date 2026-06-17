import React, { useMemo, useState } from 'react'
import { formatLogEventLabel, formatLogTime } from '../utils/accountUi'
import { SABHI_ACCOUNTS } from '../utils/sabAccountsUi.js'
import { Button } from './ui/Button.jsx'
import { SegmentedControl } from './ui/SegmentedControl.jsx'

// Distinct glyphs per level so the user can scan log severity at a glance
// instead of relying solely on background color.
const LOG_LEVEL_ICON = {
  success: '✓',
  error: '✕',
  warning: '!',
  info: '·',
}

const LogLine = React.memo(function LogLine({ entry }) {
  const level = entry.level || 'info'
  const icon = LOG_LEVEL_ICON[level] || LOG_LEVEL_ICON.info
  const event = entry.event || ''
  const text = (entry.summary || entry.fields?.detail || entry.msg || '').trim()
  return (
    <div className={`log-line log-line--${level}`}>
      <span className="log-line-icon" aria-hidden>{icon}</span>
      <time className="log-line-time">{formatLogTime(entry.time)}</time>
      {event && (
        <span className="log-line-event" title={event}>
          {formatLogEventLabel(event)}
        </span>
      )}
      <span className="log-line-msg">{text}</span>
    </div>
  )
})

// Stable key for a log entry across re-renders. Timestamp is microsecond ISO
// so duplicates are extremely rare; combine with event+account+msg-hash as a
// tiebreaker so prepending new logs doesn't invalidate every existing key
// (which would force every LogLine to remount and lose React.memo benefits).
function logKey(entry, fallback) {
  const ts = entry?.timestamp || entry?.time
  if (!ts) return `noid-${fallback}`
  const tail = (entry.msg || entry.summary || '').slice(0, 16)
  return `${ts}|${entry.account_id || ''}|${entry.event || ''}|${tail}`
}

const VISIBLE_LOG_LIMIT = 250

function isCycleBoundary(entry) {
  const event = (entry.event || '').toUpperCase()
  if (event === 'CYCLE_START' || event === 'CYCLE_RESUME') return true
  const action = (entry.action || '').toLowerCase()
  const msg = (entry.msg || '').toLowerCase()
  return action === 'cycle_start' || msg.includes('cycle_start') || msg.includes('--- cycle')
}

export function LogsToolbarTabs({ activeTab, setActiveTab, logCount, okCount, failCount }) {
  const options = [
    { value: 'logs', label: `Logs (${logCount})` },
    { value: 'success', label: `OK (${okCount})` },
    { value: 'failed', label: `Fail (${failCount})` },
  ]
  return (
    <SegmentedControl
      className="logs-toolbar-tabs"
      label="Log tabs"
      options={options}
      value={activeTab}
      onChange={setActiveTab}
    />
  )
}

export function LogPanel({
  activeTab,
  activeAccount,
  accountSlots,
  logScope,
  onLogScopeChange,
  displayLogs,
  displaySuccessList,
  displayFailedList,
  logsContainerRef,
  onScroll,
  toolbarActions,
  activeTabControl,
  connected = true,
}) {
  const [levelFilter, setLevelFilter] = useState('all') // all | issues
  const [groupByCycle, setGroupByCycle] = useState(false)
  const [showAll, setShowAll] = useState(false)

  // Reset render-cap when scope/tab/filter changes so the user always sees
  // the freshest cropped slice first.
  React.useEffect(() => { setShowAll(false) }, [activeTab, levelFilter, groupByCycle])

  const logsNewestFirst = useMemo(() => [...displayLogs].reverse(), [displayLogs])
  const successNewestFirst = useMemo(() => [...displaySuccessList].reverse(), [displaySuccessList])
  const failedNewestFirst = useMemo(() => [...displayFailedList].reverse(), [displayFailedList])

  const filteredLogs = useMemo(() => {
    let list = logsNewestFirst
    if (levelFilter === 'issues') {
      // "Errors & warnings" — most users opening this filter want to see
      // anything actionable, not strictly hard errors.
      list = list.filter(e => e.level === 'error' || e.level === 'warning')
    }
    return list
  }, [logsNewestFirst, levelFilter])

  const totalFiltered = filteredLogs.length
  const visibleLogs = useMemo(() => (
    showAll || totalFiltered <= VISIBLE_LOG_LIMIT
      ? filteredLogs
      : filteredLogs.slice(0, VISIBLE_LOG_LIMIT)
  ), [filteredLogs, showAll, totalFiltered])
  const hiddenLogCount = Math.max(0, totalFiltered - visibleLogs.length)

  const logGroups = useMemo(() => {
    if (!groupByCycle) return null
    const groups = []
    let current = { id: 0, label: 'Recent', entries: [] }
    for (const entry of visibleLogs) {
      if (isCycleBoundary(entry)) {
        if (current.entries.length) groups.push(current)
        const m = (entry.cycle != null ? String(entry.cycle) : (entry.msg || '').match(/cycle=(\d+)/i)?.[1])
        current = { id: groups.length, label: m ? `Cycle ${m}` : 'Cycle', entries: [entry] }
      } else {
        current.entries.push(entry)
      }
    }
    if (current.entries.length) groups.push(current)
    return groups.length ? groups : null
  }, [visibleLogs, groupByCycle])

  return (
    <div className="log-panel-root">
      {!connected && (
        <div className="logs-disconnected-banner" role="status" aria-live="polite">
          <span className="logs-disconnected-dot" aria-hidden />
          Live feed paused — reconnecting to server… Logs will resume automatically.
        </div>
      )}
      <div className="logs-toolbar-row logs-toolbar-row--filters">
        {toolbarActions}
        {activeTabControl}
      </div>
      {activeTab === 'logs' && (
        <div className="logs-filters">
          <div className="logs-filter-chips">
            <SegmentedControl
              label="Log scope"
              options={[
                { value: 'account', label: activeAccount || 'Account' },
                { value: 'all', label: SABHI_ACCOUNTS },
              ]}
              value={logScope}
              onChange={onLogScopeChange}
            />
            {logScope === 'all' ? (
              <span className="logs-account-chip" title="Logs from every account">
                {SABHI_ACCOUNTS} ({accountSlots?.length || 0})
              </span>
            ) : activeAccount && (
              <span className="logs-account-chip" title="Logs scoped to selected account">
                {activeAccount}
              </span>
            )}
            <SegmentedControl
              label="Filter logs"
              options={[
                { value: 'all', label: 'All levels' },
                { value: 'issues', label: 'Errors & warnings' },
              ]}
              value={levelFilter}
              onChange={setLevelFilter}
            />
          </div>
          <label className="logs-filter-toggle">
            <input type="checkbox" checked={groupByCycle} onChange={e => setGroupByCycle(e.target.checked)} />
            Group by cycle
          </label>
        </div>
      )}
      <div ref={logsContainerRef} onScroll={onScroll} className="logs-scroll">
        {activeTab === 'logs' && (
          <>
            {filteredLogs.length === 0 && (
              <div className="empty-state">
                No logs for {logScope === 'all' ? 'any account' : (activeAccount || 'this account')} yet.
              </div>
            )}
            {groupByCycle && logGroups ? (
              logGroups.map(g => (
                <details key={g.id} className="log-cycle-group" open={g.id === 0}>
                  <summary className="log-cycle-summary">
                    {g.label}
                    <span className="log-cycle-count">{g.entries.length}</span>
                  </summary>
                  <div className="log-cycle-body">
                    {g.entries.map((entry, i) => (
                      <LogLine key={logKey(entry, `${g.id}-${i}`)} entry={entry} />
                    ))}
                  </div>
                </details>
              ))
            ) : (
              visibleLogs.map((entry, i) => (
                <LogLine key={logKey(entry, i)} entry={entry} />
              ))
            )}
            {hiddenLogCount > 0 && (
              <button
                type="button"
                className="logs-show-more-btn"
                onClick={() => setShowAll(true)}
              >
                Show {hiddenLogCount} older log{hiddenLogCount === 1 ? '' : 's'}
              </button>
            )}
          </>
        )}
        {activeTab === 'success' && (
          <>
            {displaySuccessList.length === 0 && (
              <div className="empty-state">No successful forwards yet.</div>
            )}
            {successNewestFirst.map((group, i) => (
              <div key={`${group}-${i}`} className="log-result-line log-result-line--ok">
                <span>✓</span>
                <a href={`https://t.me/${group}`} target="_blank" rel="noreferrer">{group}</a>
              </div>
            ))}
          </>
        )}
        {activeTab === 'failed' && (
          <>
            {displayFailedList.length === 0 && (
              <div className="empty-state">No failures yet.</div>
            )}
            {failedNewestFirst.map((item, i) => (
              <div key={`${item.group}-${i}`} className="log-result-line log-result-line--fail">
                <span className="log-result-group">✗ {item.group}</span>
                <span className="log-result-reason">{item.reason}</span>
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  )
}

export function LogToolbarActions({
  activeTab,
  displayLogs,
  displayLogsNewestFirst,
  displaySuccessNewestFirst,
  displayFailedNewestFirst,
  clearingLogs,
  copied,
  clearDisabled = false,
  clearTitle = 'Clear logs for selected account',
  onClear,
  onCopy,
}) {
  // Per-tab "is anything to copy" check — was previously hard-coded to the
  // logs tab, so Copy on an empty Success/Fail tab would silently copy "".
  const copyEmpty =
    (activeTab === 'logs' && (displayLogs?.length ?? 0) === 0)
    || (activeTab === 'success' && (displaySuccessNewestFirst?.length ?? 0) === 0)
    || (activeTab === 'failed' && (displayFailedNewestFirst?.length ?? 0) === 0)

  return (
    <div className="logs-toolbar-actions">
      {activeTab === 'logs' && (
        <Button
          variant="danger"
          size="xs"
          className="logs-toolbar-btn logs-toolbar-btn--danger btn-with-loader"
          onClick={onClear}
          disabled={displayLogs.length === 0 || clearingLogs || clearDisabled}
          loading={clearingLogs}
          loadingLabel="Clearing…"
          title={clearTitle}
        >
          Clear
        </Button>
      )}
      <Button
        variant="toolbar"
        size="xs"
        className={`logs-toolbar-btn logs-toolbar-btn--copy${copied ? ' logs-toolbar-btn--copied' : ''}`}
        onClick={onCopy}
        disabled={copyEmpty}
        title="Copy list to clipboard"
      >
        {copied ? 'Copied' : 'Copy'}
      </Button>
    </div>
  )
}
