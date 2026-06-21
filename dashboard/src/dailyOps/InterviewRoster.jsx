import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { API } from '../config.js'
import { useAuth } from '../context/AuthContext.jsx'

const ATTENDEES = ['Nikhila', 'Bhavana', 'Tool']

const STATUS_OPTIONS = [
  { value: '', label: 'Pending', tone: 'pending' },
  { value: 'attended', label: 'Attended', tone: 'done' },
  { value: 'not_attended', label: 'Not attended', tone: 'missed' },
  { value: 'cancelled', label: 'Cancelled', tone: 'cancelled' },
  { value: 'rescheduled', label: 'Rescheduled', tone: 'rescheduled' },
]

function todayIso() {
  return new Date().toISOString().slice(0, 10)
}

function tomorrowIso() {
  const d = new Date()
  d.setDate(d.getDate() + 1)
  return d.toISOString().slice(0, 10)
}

function formatDayLabel(iso) {
  if (!iso) return '—'
  try {
    return new Date(`${iso.slice(0, 10)}T12:00:00`).toLocaleDateString('en-IN', {
      weekday: 'short',
      day: 'numeric',
      month: 'short',
      timeZone: 'Asia/Kolkata',
    })
  } catch {
    return iso
  }
}

function resolvedStatus(row) {
  return (row?.interview_attendance_status_resolved || row?.interview_attendance_status || '').trim().toLowerCase()
}

function statusTone(status) {
  const key = status === 'canceled' ? 'cancelled' : status
  return STATUS_OPTIONS.find(o => o.value === key)?.tone || 'pending'
}

function statusLabel(status) {
  const key = status === 'canceled' ? 'cancelled' : status
  return STATUS_OPTIONS.find(o => o.value === key)?.label || 'Pending'
}

function AttendanceSelect({ value, disabled, onChange, ariaLabel }) {
  return (
    <select
      className="cand-input ops-attendance-select"
      value={value || ''}
      disabled={disabled}
      onChange={e => onChange(e.target.value)}
      aria-label={ariaLabel}
    >
      {STATUS_OPTIONS.map(opt => (
        <option key={opt.value || 'pending'} value={opt.value}>{opt.label}</option>
      ))}
    </select>
  )
}

export function InterviewRoster({
  variant = 'default',
  focusDay = null,
  onFocusDayApplied,
  dashboardDay,
  onDashboardDayChange,
  dashboardFromDate,
  dashboardToDate,
  dashboardAttendeeFilter = '',
  dashboardCandidateSearch = '',
  dashboardCandidateTypeFilter = '',
  upcomingOnly = false,
  onRosterMutate,
  onRosterCountsChange,
}) {
  const { role, reference, enabled } = useAuth()
  const canManage = !enabled || role === 'admin' || role === 'handler'
  const handlerView = role === 'handler' && !!reference?.trim()
  const isDashboard = variant === 'dashboard'
  const hasRange = isDashboard && dashboardFromDate && dashboardToDate
  const isSingleDayRange = hasRange && dashboardFromDate === dashboardToDate

  const [localDay, setLocalDay] = useState(todayIso())
  const day = isDashboard ? (dashboardDay ?? localDay) : localDay
  const setDay = isDashboard ? (onDashboardDayChange ?? setLocalDay) : setLocalDay

  const [rows, setRows] = useState([])
  const [counts, setCounts] = useState({
    count: 0,
    attended_count: 0,
    not_attended_count: 0,
    pending_count: 0,
    scheduled_count: 0,
  })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState(null)
  const [attendeeFilter, setAttendeeFilter] = useState('')
  const [candidateFilter, setCandidateFilter] = useState('')
  const [channelFilter, setChannelFilter] = useState('')
  const [candidateOptions, setCandidateOptions] = useState([])

  const rosterCountsRef = useRef(onRosterCountsChange)
  rosterCountsRef.current = onRosterCountsChange

  const effectiveAttendee = isDashboard ? dashboardAttendeeFilter : attendeeFilter
  const effectiveSearch = isDashboard ? dashboardCandidateSearch : candidateFilter
  const effectiveChannel = isDashboard ? dashboardCandidateTypeFilter : channelFilter

  const load = useCallback(async ({ silent = false } = {}) => {
    if (!silent) setLoading(true)
    try {
      const params = new URLSearchParams()
      let url = `${API}/candidates/interviews/daily`
      if (hasRange && !isSingleDayRange) {
        url = `${API}/candidates/interviews/monitor`
        params.set('from', dashboardFromDate)
        params.set('to', dashboardToDate)
      } else {
        params.set('date', hasRange ? dashboardFromDate : day)
      }
      if (effectiveAttendee) params.set('attendee', effectiveAttendee)
      const search = effectiveSearch.trim()
      if (search) params.set('search', search)
      if (effectiveChannel) params.set('channel', effectiveChannel)
      if (upcomingOnly) params.set('upcoming_only', 'true')

      const res = await fetch(`${url}?${params}`, { credentials: 'include' })
      if (!(res.headers.get('content-type') || '').includes('application/json')) {
        throw new Error(`Server returned ${res.status} — hard refresh and try again`)
      }
      const data = await res.json()
      if (!res.ok || data.status !== 'ok') {
        throw new Error(data.message || data.detail || `Failed to load roster (${res.status})`)
      }
      setRows(data.interviews || [])
      const nextCounts = {
        count: data.count || 0,
        attended_count: data.attended_count || 0,
        not_attended_count: data.not_attended_count || 0,
        pending_count: data.pending_count || 0,
        scheduled_count: data.scheduled_count || 0,
      }
      setCounts(nextCounts)
      rosterCountsRef.current?.(nextCounts, { isUpcomingView: upcomingOnly })
      setError('')
    } catch (err) {
      if (!silent) {
        setError(err.message || 'Failed to load')
        setRows([])
      }
    } finally {
      if (!silent) setLoading(false)
    }
  }, [
    day,
    dashboardFromDate,
    dashboardToDate,
    effectiveAttendee,
    effectiveSearch,
    effectiveChannel,
    hasRange,
    isSingleDayRange,
    upcomingOnly,
  ])

  const loadCandidateOptions = useCallback(async () => {
    if (hasRange) return
    try {
      const params = new URLSearchParams({ from: day, to: day })
      if (attendeeFilter) params.set('attendee', attendeeFilter)
      if (channelFilter) params.set('channel', channelFilter)
      const res = await fetch(`${API}/candidates/interviews/filter-options?${params}`, { credentials: 'include' })
      if (!(res.headers.get('content-type') || '').includes('application/json')) return
      const data = await res.json()
      if (!res.ok || data.status !== 'ok') return
      setCandidateOptions(data.options || [])
    } catch {
      setCandidateOptions([])
    }
  }, [day, attendeeFilter, channelFilter, hasRange])

  useEffect(() => { load() }, [load])
  useEffect(() => { loadCandidateOptions() }, [loadCandidateOptions])
  useEffect(() => {
    if (focusDay) {
      setDay(focusDay.slice(0, 10))
      onFocusDayApplied?.()
    }
  }, [focusDay, onFocusDayApplied, setDay])

  async function saveAttendance(row, status, attendee) {
    setBusyId(row.id)
    setError('')
    try {
      const body = { status: status || '', remark: row.interview_attendance_remark || '' }
      if (status && (status === 'attended' || status === 'not_attended')) {
        body.attendee = attendee || row.interview_attended_by || reference || ATTENDEES[0]
      }
      const res = await fetch(`${API}/candidates/${row.id}/interview-attendance`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const data = await res.json()
      if (!res.ok || data.status !== 'ok') throw new Error(data.message || 'Update failed')
      await load({ silent: true })
      onRosterMutate?.()
    } catch (err) {
      setError(err.message || 'Update failed')
    } finally {
      setBusyId(null)
    }
  }

  const title = isDashboard
    ? (hasRange && dashboardFromDate !== dashboardToDate
      ? `${formatDayLabel(dashboardFromDate)} – ${formatDayLabel(dashboardToDate)}`
      : formatDayLabel(dashboardFromDate || day))
    : "Today's interview roster"

  const scopeHint = handlerView
    ? `${reference} — your interview roster`
    : effectiveAttendee
      ? `Attendee: ${effectiveAttendee}`
      : 'All handlers'

  return (
    <section className={isDashboard ? 'ops-dash-roster' : 'admin-card admin-card--full ops-interview-roster'}>
      <header className={isDashboard ? 'ops-dash-roster__head' : 'ops-checklist-header'}>
        {isDashboard ? (
          <>
            <div className="ops-dash-roster__title">
              <h2>{title}</h2>
              <p className="ops-dash-roster__meta">
                <strong>{counts.count}</strong> scheduled
                {counts.pending_count > 0 && (
                  <> · <strong>{counts.pending_count}</strong> pending</>
                )}
              </p>
            </div>
          </>
        ) : (
          <>
            <div>
              <h2>{title}</h2>
              <p className="admin-hint">
                <strong>{scopeHint}</strong> · <strong>{formatDayLabel(day)}</strong>
                {' · '}<strong>{counts.attended_count}</strong> attended · <strong>{counts.count}</strong> scheduled
              </p>
            </div>
            <div className="ops-checklist-header-actions">
              <input
                className="cand-input ops-checklist-date"
                type="date"
                value={day}
                onChange={e => setDay(e.target.value)}
                aria-label="Interview day"
              />
              <select
                className="cand-input ops-checklist-ref-select"
                value={attendeeFilter}
                onChange={e => setAttendeeFilter(e.target.value)}
                aria-label="Filter by attendee"
              >
                <option value="">All attendees</option>
                {ATTENDEES.map(name => <option key={name} value={name}>{name}</option>)}
              </select>
              <select
                className="cand-input ops-checklist-ref-select"
                value={candidateFilter}
                onChange={e => setCandidateFilter(e.target.value)}
                aria-label="Filter by candidate name"
              >
                <option value="">All candidates</option>
                {candidateOptions.map(({ value, label }) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
              {canManage && (
                <>
                  <button type="button" className="btn btn--primary btn--sm" onClick={() => setDay(tomorrowIso())}>
                    + Add slot for tomorrow
                  </button>
                </>
              )}
              <button type="button" className="btn btn--ghost btn--sm" onClick={() => load()}>Refresh</button>
            </div>
          </>
        )}
      </header>

      {error && <p className="admin-error" role="alert">{error}</p>}

      {loading && rows.length === 0 ? (
        <p className="ops-checklist-empty">Loading interview roster…</p>
      ) : rows.length === 0 ? (
        <p className="ops-checklist-empty">No interview slots for this day.</p>
      ) : (
        <div className={`ops-interview-table-wrap ta-table-responsive ta-table-responsive--cards${isDashboard ? ' ops-dash-table-wrap' : ' ops-interview-table-wrap--bounded'}`}>
          <div className="ta-table-responsive__scroll">
            <table className={`ops-interview-table${isDashboard ? ' ops-dash-table ops-dash-table--v3' : ''}`}>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Candidate</th>
                  <th>Technology</th>
                  {!handlerView && !effectiveAttendee && <th>Attendee</th>}
                  <th>Attendance</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(row => {
                  const status = resolvedStatus(row)
                  return (
                    <tr key={row.id} className={`ops-interview-row ops-interview-row--${statusTone(status)}`}>
                      <td data-label="Time" className="ops-interview-time">
                        {[row.time, row.time_end].filter(Boolean).join(' – ') || '—'}
                      </td>
                      <td data-label="Candidate">
                        <strong>{row.name}</strong>
                        {row.phone && <span className="ops-interview-phone">{row.phone}</span>}
                      </td>
                      <td data-label="Technology">{row.technology || '—'}</td>
                      {!handlerView && !effectiveAttendee && (
                        <td data-label="Attendee">{row.interview_attended_by || row.reference || '—'}</td>
                      )}
                      <td data-label="Attendance" className="ops-interview-attendance-cell">
                        <div className="ops-interview-attendance-form">
                          <AttendanceSelect
                            value={status === 'pending' ? '' : status}
                            disabled={busyId === row.id}
                            ariaLabel={`Attendance for ${row.name}`}
                            onChange={val => saveAttendance(row, val, row.interview_attended_by)}
                          />
                          <span className={`ops-status-pill ops-status-pill--${statusTone(status)}`}>
                            {statusLabel(status)}
                          </span>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  )
}
