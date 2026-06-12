import React from 'react'
import { Spinner } from '../Loader.jsx'
import { useConfirm } from '../context/ConfirmContext.jsx'
import { Button } from './ui/Button.jsx'

export function GlobalActions({
  connected,
  canStartMore,
  anyRunning,
  bulkActionLoading,
  hardRefreshing,
  totalListLoading,
  onStartAll,
  onStopAll,
  onHardRefresh,
  onTotalList,
}) {
  const { confirm } = useConfirm()

  async function handleStopAll() {
    const ok = await confirm({
      title: 'Stop all accounts?',
      message: 'All running workers will stop. You can start them again when ready.',
      confirmLabel: 'Stop all',
      cancelLabel: 'Keep running',
      variant: 'danger',
    })
    if (ok) onStopAll()
  }

  return (
    <div className="app-header-actions">
      <div className="app-header-right-group app-header-right-group--primary">
        {anyRunning ? (
          <Button
            variant="danger"
            className="app-header-btn"
            onClick={handleStopAll}
            disabled={bulkActionLoading}
            loading={bulkActionLoading === 'stop'}
            loadingLabel="Stopping…"
            title="Stop all running accounts"
          >
            <span className="app-header-btn-icon" aria-hidden>⏹</span>
            <span className="app-header-btn-label">Stop All</span>
          </Button>
        ) : (
          <Button
            variant="success"
            className="app-header-btn"
            onClick={onStartAll}
            disabled={!canStartMore || bulkActionLoading}
            loading={bulkActionLoading === 'start'}
            loadingLabel="Starting…"
            title={
              canStartMore
                ? 'Start all logged-in idle accounts (24/7)'
                : 'No logged-in accounts ready to start'
            }
          >
            <span className="app-header-btn-icon" aria-hidden>▶</span>
            <span className="app-header-btn-label">Start All</span>
          </Button>
        )}
      </div>
      <div className="app-header-right-group app-header-right-group--status">
        <div className="connection-pill app-header-control" title={connected ? 'Live updates from backend' : 'Cannot reach backend — retrying every 3s'}>
          <span className={`connection-dot${connected ? ' connection-dot--on' : ''}`} />
          {!connected && <Spinner size={12} />}
          <span className="connection-label">
            {connected ? 'Connected' : 'Reconnecting…'}
          </span>
        </div>
      </div>
      {onTotalList && (
        <div className="app-header-right-group app-header-right-group--secondary">
          <Button
            variant="ghost"
            className="app-header-btn"
            onClick={onTotalList}
            disabled={totalListLoading}
            loading={totalListLoading}
            loadingLabel="Building list…"
            title="Fetch every joined group/channel from all logged-in accounts and download as CSV"
          >
            <span className="app-header-btn-icon" aria-hidden>📋</span>
            <span className="app-header-btn-label">Total List</span>
          </Button>
        </div>
      )}
      <div className="app-header-right-group app-header-right-group--secondary">
        <Button
          variant="ghost"
          className="app-header-btn"
          onClick={onHardRefresh}
          disabled={hardRefreshing}
          loading={hardRefreshing}
          loadingLabel="Refreshing…"
          title="Full page reload + latest server state"
        >
          <span className="app-header-btn-icon" aria-hidden>↻</span>
          <span className="app-header-btn-label">Hard Refresh</span>
        </Button>
      </div>
    </div>
  )
}
