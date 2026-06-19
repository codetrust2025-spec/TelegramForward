import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { API } from '../config.js'
import { useAuth } from '../context/AuthContext.jsx'
import { InterviewRoster } from './InterviewRoster.jsx'
import {
  navigatePendingWorkToCandidates,
  usePendingWorksContext,
} from './PendingWorksProvider.jsx'

function todayIso() {
  return new Date().toISOString().slice(0, 10)
}

function weekAgoIso() {
  const d = new Date()
  d.setDate(d.getDate() - 7)
  return d.toISOString().slice(0, 10)
}

function PendingWorksStrip({ onOpenCandidates, maxPreview = 4 }) {
  const { works, count, candidateCount, loading, error } = usePendingWorksContext()
  const preview = useMemo(() => works.slice(0, maxPreview), [works, maxPreview])

  if (!loading && count === 0) return null

  return (
    <section className="pending-works-strip" aria-label="Pending works">
      <div className="pending-works-strip__row">
        <span className="pending-works-strip__pulse" aria-hidden />
        <div className="pending-works-strip__text">
          <strong className="pending-works-strip__title">Pending works</strong>
          <span className="pending-works-strip__meta">
            {loading
              ? 'Checking…'
              : `${count} task${count === 1 ? '' : 's'} · ${candidateCount} candidate${candidateCount === 1 ? '' : 's'}`}
          </span>
        </div>
        {!loading && count > 0 && (
          <button
            type="button"
            className="pending-works-strip__cta"
            onClick={() => navigatePendingWorkToCandidates(null, { onNavCandidates: onOpenCandidates })}
          >
            Open
          </button>
        )}
      </div>
      {error && <p className="pending-works-strip__error" role="alert">{error}</p>}
      {!loading && preview.length > 0 && (
        <div className="pending-works-strip__chips">
          {preview.map(work => (
            <button
              type="button"
              key={work.id || `${work.candidate_name}-${work.label}`}
              className="pending-works-strip__chip"
              title={work.label}
              onClick={() => navigatePendingWorkToCandidates(work, { onNavCandidates: onOpenCandidates })}
            >
              {work.candidate_name || work.label}
            </button>
          ))}
          {works.length > maxPreview && (
            <button
              type="button"
              className="pending-works-strip__chip pending-works-strip__chip--more"
              onClick={() => navigatePendingWorkToCandidates(null, { onNavCandidates: onOpenCandidates })}
            >
              +{works.length - maxPreview} more
            </button>
          )}
        </div>
      )}
    </section>
  )
}

function KpiCard({ label, value, tone = 'default', loading = false }) {
  return (
    <div className={`ops-dash-kpi ops-dash-kpi--${tone}${loading ? ' ops-dash-kpi--loading' : ''}`}>
      <span className="ops-dash-kpi__label">{label}</span>
      <strong className="ops-dash-kpi__value">{loading ? '…' : value}</strong>
    </div>
  )
}

export function DailyOpsPanel({
  loggedInSlots = [],
  activeAccount,
  accountInfo = {},
  onSelectAccount,
  onStartAll,
  startAllBusy = false,
  showFleetControls = false,
  onNavCandidates,
}) {
  const { role, reference } = useAuth()
  const handlerScoped = role === 'handler' && !!reference?.trim()

  const [fromDate, setFromDate] = useState(weekAgoIso())
  const [toDate, setToDate] = useState(todayIso())
  const [attendeeFilter, setAttendeeFilter] = useState(handlerScoped ? reference : '')
  const [candidateSearch, setCandidateSearch] = useState('')
  const [globalStats, setGlobalStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [rosterCounts, setRosterCounts] = useState(null)

  const loadGlobal = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams({ from: fromDate, to: toDate })
      if (attendeeFilter) params.set('attendee', attendeeFilter)
      const search = candidateSearch.trim()
      if (search) params.set('search', search)
      const res = await fetch(`${API}/candidates/interviews/global?${params}`, { credentials: 'include' })
      if (!(res.headers.get('content-type') || '').includes('application/json')) {
        throw new Error(`Global data ${res.status}`)
      }
      const data = await res.json()
      if (!res.ok || data.status !== 'ok') throw new Error(data.message || 'Failed to load global data')
      setGlobalStats(data)
      setError('')
    } catch (err) {
      setError(err.message || 'Failed to load dashboard')
    } finally {
      setLoading(false)
    }
  }, [fromDate, toDate, attendeeFilter, candidateSearch])

  useEffect(() => { loadGlobal() }, [loadGlobal])

  const interviews = globalStats?.interviews || rosterCounts || {}

  return (
    <div className="daily-ops-page daily-ops-page--dashboard">
      <PendingWorksStrip onOpenCandidates={onNavCandidates} />

      <div className="ops-dashboard ops-dashboard--v3">
        <header className="ops-dash-toolbar">
          <div>
            <h1 className="ops-dash-title">Daily ops</h1>
            <p className="ops-dash-sub">Interview roster, attendance, and pending work</p>
          </div>
          <div className="ops-dash-toolbar__filters">
            <input className="cand-input" type="date" value={fromDate} onChange={e => setFromDate(e.target.value)} aria-label="From date" />
            <input className="cand-input" type="date" value={toDate} onChange={e => setToDate(e.target.value)} aria-label="To date" />
            {!handlerScoped && (
              <input
                className="cand-input"
                placeholder="Filter attendee"
                value={attendeeFilter}
                onChange={e => setAttendeeFilter(e.target.value)}
                aria-label="Attendee filter"
              />
            )}
            <input
              className="cand-input"
              placeholder="Search candidate"
              value={candidateSearch}
              onChange={e => setCandidateSearch(e.target.value)}
              aria-label="Candidate search"
            />
            <button type="button" className="btn btn--ghost btn--sm" onClick={loadGlobal}>Refresh</button>
          </div>
        </header>

        {error && <p className="admin-error ops-dash-error" role="alert">{error}</p>}

        <div className="ops-dash-kpi-row ops-dash-kpi-row--v3" aria-label="Summary metrics">
          <KpiCard label="Scheduled" value={interviews.count ?? 0} tone="blue" loading={loading} />
          <KpiCard label="Attended" value={interviews.attended_count ?? 0} tone="green" loading={loading} />
          <KpiCard label="Pending" value={interviews.pending_count ?? 0} tone="amber" loading={loading} />
          <KpiCard label="Not attended" value={interviews.not_attended_count ?? 0} tone="red" loading={loading} />
        </div>

        {showFleetControls && loggedInSlots.length > 0 && (
          <div className="ops-dash-fleet-hint">
            Fleet: {loggedInSlots.length} logged-in account{loggedInSlots.length === 1 ? '' : 's'}
            {activeAccount && accountInfo?.[activeAccount] && (
              <> · active {accountInfo[activeAccount].display_name || activeAccount}</>
            )}
          </div>
        )}

        <InterviewRoster
          key={`${fromDate}|${toDate}`}
          variant="dashboard"
          dashboardFromDate={fromDate}
          dashboardToDate={toDate}
          dashboardAttendeeFilter={attendeeFilter}
          dashboardCandidateSearch={candidateSearch}
          onRosterCountsChange={setRosterCounts}
          onRosterMutate={loadGlobal}
        />
      </div>
    </div>
  )
}
