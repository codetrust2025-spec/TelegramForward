import React, { useCallback, useEffect, useState } from 'react'
import { API } from '../config.js'
import { useAuth } from '../context/AuthContext.jsx'
import { InterviewRoster } from './InterviewRoster.jsx'
import { PendingWorksStrip } from './PendingWorksStrip.jsx'
import { PRESETS, detectPresetFromRange, resolvePresetRange } from './dateRangePresets.js'

const ATTENDEES = ['Nikhila', 'Bhavana', 'Tool']

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
  // Daily Ops is shared across all authenticated operators.  Do not prefill
  // a handler's own name as an attendee filter or their roster looks empty
  // whenever another handler owns the booked slot.
  const handlerScoped = false

  const initialRange = resolvePresetRange('upcoming')
  const [fromDate, setFromDate] = useState(initialRange.from)
  const [toDate, setToDate] = useState(initialRange.to)
  const [rangePreset, setRangePreset] = useState('upcoming')
  const [attendeeFilter, setAttendeeFilter] = useState('')
  const [candidateSearch, setCandidateSearch] = useState('')
  const [globalStats, setGlobalStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [rosterCounts, setRosterCounts] = useState(null)

  const upcomingOnly = rangePreset === 'upcoming'

  function applyPreset(presetId) {
    const range = resolvePresetRange(presetId)
    if (!range) return
    setRangePreset(presetId)
    setFromDate(range.from)
    setToDate(range.to)
  }

  function applyManualFrom(value) {
    setFromDate(value)
    setRangePreset(detectPresetFromRange(value, toDate))
  }

  function applyManualTo(value) {
    setToDate(value)
    setRangePreset(detectPresetFromRange(fromDate, value))
  }

  // When range is custom, disable upcoming_only filter to show all interviews in the range
  const effectiveUpcomingOnly = rangePreset === 'upcoming' ? upcomingOnly : false

  const loadGlobal = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams({ from: fromDate, to: toDate })
      if (attendeeFilter) params.set('attendee', attendeeFilter)
      const search = candidateSearch.trim()
      if (search) params.set('search', search)
      if (effectiveUpcomingOnly) params.set('upcoming_only', 'true')
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
  }, [fromDate, toDate, attendeeFilter, candidateSearch, effectiveUpcomingOnly])

  useEffect(() => { loadGlobal() }, [loadGlobal])

  const interviews = globalStats?.interviews || rosterCounts || {}

  return (
    <div className="daily-ops-page daily-ops-page--dashboard">
      <PendingWorksStrip onOpenCandidates={onNavCandidates} />

      <div className="ops-dashboard ops-dashboard--v3">
        <header className="ops-dash-toolbar ops-dash-toolbar--v3 ops-dash-toolbar--legacy">
          <div className="ops-dash-toolbar__intro">
            <h1 className="ops-dash-title">Daily ops</h1>
            <p className="ops-dash-sub">Interview roster, attendance, and pending work</p>
          </div>
          <div className="ops-dash-toolbar__main ops-dash-toolbar__main--legacy">
            <div className="ops-date-range">
              <div className="ops-date-range__presets" role="tablist" aria-label="Date range">
                {PRESETS.map(preset => (
                  <button
                    key={preset.id}
                    type="button"
                    role="tab"
                    aria-selected={rangePreset === preset.id}
                    className={`ops-date-range__preset${rangePreset === preset.id ? ' ops-date-range__preset--active' : ''}`}
                    onClick={() => applyPreset(preset.id)}
                  >
                    {preset.label}
                  </button>
                ))}
              </div>
              <div className="ops-date-range__inputs">
                <span className="ops-date-range__label">Range</span>
                <input className="cand-input" type="date" value={fromDate} onChange={e => applyManualFrom(e.target.value)} aria-label="From date" />
                <span className="ops-date-range__sep">—</span>
                <input className="cand-input" type="date" value={toDate} onChange={e => applyManualTo(e.target.value)} aria-label="To date" />
              </div>
            </div>
            {!handlerScoped && (
              <select
                className="cand-input"
                value={attendeeFilter}
                onChange={e => setAttendeeFilter(e.target.value)}
                aria-label="Attendee filter"
              >
                <option value="">All attendees</option>
                {ATTENDEES.map(name => (
                  <option key={name} value={name}>{name}</option>
                ))}
              </select>
            )}
            <input
              className="cand-input"
              placeholder="Search candidate"
              value={candidateSearch}
              onChange={e => setCandidateSearch(e.target.value)}
              aria-label="Candidate search"
            />
            <div className="ops-dash-toolbar__actions">
              <button type="button" className="btn btn--ghost btn--sm" onClick={loadGlobal}>Refresh</button>
            </div>
          </div>
        </header>

        {error && <p className="admin-error ops-dash-error" role="alert">{error}</p>}

        <div className="ops-dash-kpi-row ops-dash-kpi-row--v3" aria-label="Summary metrics">
          <KpiCard label="Scheduled" value={interviews.count ?? 0} tone="blue" loading={loading} />
          <KpiCard label="Attended" value={interviews.attended_count ?? 0} tone="green" loading={loading} />
          <KpiCard label="Pending" value={interviews.pending_count ?? 0} tone="amber" loading={loading} />
          <KpiCard label="Not attended" value={interviews.not_attended_count ?? 0} tone="red" loading={loading} />
        </div>

        <InterviewRoster
          key={`${fromDate}|${toDate}|${upcomingOnly}`}
          variant="dashboard"
          dashboardFromDate={fromDate}
          dashboardToDate={toDate}
          dashboardAttendeeFilter={attendeeFilter}
          dashboardCandidateSearch={candidateSearch}
          upcomingOnly={upcomingOnly}
          onRosterCountsChange={setRosterCounts}
          onRosterMutate={loadGlobal}
        />
      </div>
    </div>
  )
}
