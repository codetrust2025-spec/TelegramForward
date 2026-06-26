import React, { useCallback, useEffect, useState } from 'react'
import { API } from '../config.js'
import { useAuth } from '../context/AuthContext.jsx'
import { InterviewRoster } from './InterviewRoster.jsx'
import { PendingWorksStrip } from './PendingWorksStrip.jsx'
import { PRESETS, detectPresetFromRange, resolvePresetRange } from './dateRangePresets.js'

const ATTENDEES = ['Nikhila', 'Bhavana', 'Tool']
const ROUNDS = ['L1', 'L2', 'HR', 'Final', 'Screening']

function KpiCard({ label, value, tone = 'default', loading = false, active = false, onClick }) {
  return (
    <button
      type="button"
      className={`ops-dash-kpi ops-dash-kpi--${tone}${loading ? ' ops-dash-kpi--loading' : ''}${active ? ' ops-dash-kpi--active' : ''}`}
      onClick={onClick}
      aria-pressed={active}
    >
      <span className="ops-dash-kpi__label">{label}</span>
      <strong className="ops-dash-kpi__value">{loading ? '…' : value}</strong>
    </button>
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
  const [roundFilter, setRoundFilter] = useState('')
  const [technologyFilter, setTechnologyFilter] = useState('')
  const [candidateSearch, setCandidateSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
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
      if (roundFilter) params.set('round', roundFilter)
      if (technologyFilter) params.set('technology', technologyFilter)
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
  }, [fromDate, toDate, attendeeFilter, roundFilter, technologyFilter, candidateSearch, effectiveUpcomingOnly])

  useEffect(() => { loadGlobal() }, [loadGlobal])

  const interviews = globalStats?.interviews || rosterCounts || {}
  const technologyOptions = Object.keys(globalStats?.by_technology || {}).sort()

  return (
    <div className="daily-ops-page daily-ops-page--dashboard">

      {/* ── Compact top bar: title + KPIs + pending pill ─────────────── */}
      <div className="ops-topbar">
        <div className="ops-topbar__left">
          <h1 className="ops-dash-title">Daily ops</h1>
          <span className="ops-dash-sub ops-topbar__sub">Interview roster</span>
        </div>

        <div className="ops-topbar__kpis">
          <KpiCard label="Scheduled"    value={interviews.count             ?? 0} tone="blue"  loading={loading} active={statusFilter === ''} onClick={() => setStatusFilter('')} />
          <KpiCard label="Attended"     value={interviews.attended_count    ?? 0} tone="green" loading={loading} active={statusFilter === 'attended'} onClick={() => setStatusFilter(statusFilter === 'attended' ? '' : 'attended')} />
          <KpiCard label="Pending"      value={interviews.pending_count     ?? 0} tone="amber" loading={loading} active={statusFilter === 'pending'} onClick={() => setStatusFilter(statusFilter === 'pending' ? '' : 'pending')} />
          <KpiCard label="Not attended" value={interviews.not_attended_count ?? 0} tone="red"   loading={loading} active={statusFilter === 'not_attended'} onClick={() => setStatusFilter(statusFilter === 'not_attended' ? '' : 'not_attended')} />
        </div>

        <div className="ops-topbar__right">
          <PendingWorksStrip compact onOpenCandidates={onNavCandidates} />
        </div>
      </div>

      {/* ── Controls row: all filters in one line ───────────────────── */}
      <div className="ops-dash-controls-row">
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
          <input className="cand-input ops-ctrl-date" type="date" value={fromDate} onChange={e => applyManualFrom(e.target.value)} aria-label="From date" />
          <span className="ops-date-range__sep">—</span>
          <input className="cand-input ops-ctrl-date" type="date" value={toDate}   onChange={e => applyManualTo(e.target.value)}   aria-label="To date" />
        </div>

        {!handlerScoped && (
          <select
            className="cand-input ops-ctrl-select"
            value={attendeeFilter}
            onChange={e => setAttendeeFilter(e.target.value)}
            aria-label="Attendee filter"
          >
            <option value="">All attendees</option>
            {ATTENDEES.map(name => <option key={name} value={name}>{name}</option>)}
          </select>
        )}
        <select
          className="cand-input ops-ctrl-select"
          value={roundFilter}
          onChange={e => setRoundFilter(e.target.value)}
          aria-label="Round filter"
        >
          <option value="">All rounds</option>
          {ROUNDS.map(r => <option key={r} value={r}>{r}</option>)}
        </select>
        <select
          className="cand-input ops-ctrl-select"
          value={technologyFilter}
          onChange={e => setTechnologyFilter(e.target.value)}
          aria-label="Technology filter"
        >
          <option value="">All profiles</option>
          {technologyOptions.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <input
          className="cand-input ops-ctrl-search"
          placeholder="Search candidate"
          value={candidateSearch}
          onChange={e => setCandidateSearch(e.target.value)}
          aria-label="Candidate search"
        />
        <button type="button" className="btn btn--ghost btn--sm ops-ctrl-refresh" onClick={loadGlobal}>
          Refresh
        </button>
      </div>

      {error && <p className="admin-error ops-dash-error" role="alert">{error}</p>}

      {/* ── Table fills the rest ─────────────────────────────────────── */}
      <div className="ops-dashboard ops-dashboard--v3 ops-table-area">
        <InterviewRoster
          key={`${fromDate}|${toDate}|${upcomingOnly}`}
          variant="dashboard"
          dashboardFromDate={fromDate}
          dashboardToDate={toDate}
          dashboardAttendeeFilter={attendeeFilter}
          dashboardRoundFilter={roundFilter}
          dashboardTechnologyFilter={technologyFilter}
          dashboardCandidateSearch={candidateSearch}
          dashboardStatusFilter={statusFilter}
          upcomingOnly={upcomingOnly}
          onRosterCountsChange={setRosterCounts}
          onRosterMutate={loadGlobal}
        />
      </div>
    </div>
  )
}
