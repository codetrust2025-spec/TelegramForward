import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { API } from '../config.js'
import { useAuth } from '../context/AuthContext.jsx'
import { useConfirm } from '../context/ConfirmContext.jsx'
import { formatClockTime } from '../utils/istTime.js'

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

function RowActions({ row, busy, canEditAttendee, onEditAttendee, onEditSlot, onRemove }) {
  const [open, setOpen] = useState(false)
  const [position, setPosition] = useState(null)
  const triggerRef = useRef(null)
  const menuRef = useRef(null)
  useEffect(() => {
    if (!open) return undefined
    function closeOnOutsideClick(event) {
      if (!triggerRef.current?.contains(event.target) && !menuRef.current?.contains(event.target)) setOpen(false)
    }
    function closeOnEscape(event) { if (event.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', closeOnOutsideClick)
    document.addEventListener('keydown', closeOnEscape)
    return () => { document.removeEventListener('mousedown', closeOnOutsideClick); document.removeEventListener('keydown', closeOnEscape) }
  }, [open])
  function toggleMenu() {
    if (open) { setOpen(false); return }
    const rect = triggerRef.current?.getBoundingClientRect()
    if (rect) setPosition({ top: rect.bottom + 4, left: Math.max(8, rect.right - 196) })
    setOpen(true)
  }
  const menu = open && position && createPortal(
    <ul ref={menuRef} className="ops-row-menu__list ops-row-menu__list--portal" style={{ top: position.top, left: position.left }} role="menu">
      {canEditAttendee && <li role="none"><button type="button" role="menuitem" className="ops-row-menu__item" onClick={() => { setOpen(false); onEditAttendee(row) }}>Edit attendee</button></li>}
      <li role="none"><button type="button" role="menuitem" className="ops-row-menu__item" onClick={() => { setOpen(false); onEditSlot(row) }}>Edit slot</button></li>
      <li role="none"><button type="button" role="menuitem" className="ops-row-menu__item ops-row-menu__item--danger" onClick={() => { setOpen(false); onRemove(row) }}>Remove slot</button></li>
    </ul>, document.body)
  return (
    <div className="ops-row-menu">
      <button ref={triggerRef} type="button" className="ops-row-menu__trigger" aria-label={`Actions for ${row.name}`} aria-haspopup="menu" aria-expanded={open} disabled={busy} onClick={toggleMenu}>⋮</button>
      {menu}
    </div>
  )
}

function SlotEditModal({ row, mode, busy, onClose, onSave }) {
  const [attendee, setAttendee] = useState(row.interview_attendee_resolved || row.interview_attendee || 'Bhavana')
  const [date, setDate] = useState(row.date || '')
  const [time, setTime] = useState(row.time || '')
  const [timeEnd, setTimeEnd] = useState(row.time_end || '')
  const [notes, setNotes] = useState(row.notes || '')
  const [error, setError] = useState('')
  const attendeeOnly = mode === 'attendee'
  async function submit(event) {
    event.preventDefault()
    setError('')
    try {
      await onSave(attendeeOnly ? { attendee } : { date, time, time_end: timeEnd, notes, interview_round: row.interview_round || '' })
    } catch (err) {
      setError(err.message || 'Save failed')
    }
  }
  return (
    <div className="cand-modal-backdrop" onMouseDown={event => event.target === event.currentTarget && onClose()}>
      <form className="cand-modal ops-slot-modal" onSubmit={submit}>
        <header className="cand-modal-header"><div><h3 className="cand-modal-title">{attendeeOnly ? 'Edit attendee' : 'Edit interview slot'}</h3><p className="cand-modal-sub">{row.name}</p></div><button type="button" className="cand-modal-close" onClick={onClose} aria-label="Close">×</button></header>
        <div className="cand-modal-body">
          {attendeeOnly ? <label className="cand-field cand-field--span2"><span className="cand-field-label">Attendee</span><input className="cand-input" list="ops-attendee-options" value={attendee} onChange={event => setAttendee(event.target.value)} required autoFocus /><datalist id="ops-attendee-options">{ATTENDEES.map(name => <option key={name} value={name} />)}</datalist></label> : <><label className="cand-field"><span className="cand-field-label">Date</span><input className="cand-input" type="date" value={date} onChange={event => setDate(event.target.value)} required /></label><label className="cand-field"><span className="cand-field-label">Start time</span><input className="cand-input" type="time" value={time} onChange={event => setTime(event.target.value)} required /></label><label className="cand-field"><span className="cand-field-label">End time</span><input className="cand-input" type="time" value={timeEnd} onChange={event => setTimeEnd(event.target.value)} required /></label><label className="cand-field cand-field--span2"><span className="cand-field-label">Notes</span><input className="cand-input" value={notes} onChange={event => setNotes(event.target.value)} /></label></>}
          {error && <p className="admin-error cand-field--span2">{error}</p>}
        </div>
        <footer className="cand-modal-footer"><button type="button" className="cand-btn cand-btn--ghost" onClick={onClose} disabled={busy}>Cancel</button><button type="submit" className="cand-btn cand-btn--primary" disabled={busy}>{busy ? 'Saving…' : 'Save changes'}</button></footer>
      </form>
    </div>
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
  dashboardStatusFilter = '',
  upcomingOnly = false,
  onRosterMutate,
  onRosterCountsChange,
}) {
  const { role, enabled, reference } = useAuth()
  const { confirm } = useConfirm()
  const canManage = !enabled || role === 'admin' || role === 'handler'
  const canEditAttendee = !enabled || role === 'admin'
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
  const [editing, setEditing] = useState(null)
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

      const res = await fetch(`${url}?${params}`, { credentials: 'include', cache: 'no-store' })
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
  useEffect(() => {
    const timer = setInterval(() => load({ silent: true }), 5000)
    return () => clearInterval(timer)
  }, [load])
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
        // Attendee is the support person, never the referrer or the operator
        // recording attendance. Bhavana is the safe default for all slots.
        body.attendee = attendee || row.interview_attendee_resolved || row.interview_attendee || 'Bhavana'
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

  async function saveAttendee(row, attendee) {
    setBusyId(row.id)
    try {
      const res = await fetch(`${API}/candidates/${row.id}/interview-attendee`, {
        method: 'PATCH', credentials: 'include', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ attendee }),
      })
      const data = await res.json()
      if (!res.ok || data.status !== 'ok') throw new Error(data.message || 'Update failed')
      setEditing(null)
      await load({ silent: true })
      onRosterMutate?.()
    } finally { setBusyId(null) }
  }

  async function saveSlot(row, values) {
    setBusyId(row.id)
    try {
      const res = await fetch(`${API}/candidates/interviews/slots/${row.id}`, {
        method: 'PATCH', credentials: 'include', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(values),
      })
      const data = await res.json()
      if (!res.ok || data.status !== 'ok') throw new Error(data.message || 'Update failed')
      setEditing(null)
      await load({ silent: true })
      onRosterMutate?.()
    } finally { setBusyId(null) }
  }

  async function removeSlot(row) {
    const ok = await confirm({
      title: 'Remove interview slot?',
      message: `Remove slot for ${row.name}? The candidate record stays in Candidates.`,
      confirmLabel: 'Remove',
      variant: 'danger',
    })
    if (!ok) return
    setBusyId(row.id)
    setError('')
    try {
      const res = await fetch(`${API}/candidates/interviews/slots/${row.id}`, { method: 'DELETE', credentials: 'include' })
      const data = await res.json()
      if (!res.ok || data.status !== 'ok') throw new Error(data.message || 'Remove failed')
      await load({ silent: true })
      onRosterMutate?.()
    } catch (err) { setError(err.message || 'Remove failed') } finally { setBusyId(null) }
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
      {!isDashboard && (
      <header className="ops-checklist-header">
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
      </header>
      )}

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
                  <th>Date</th>
                  <th>Time</th>
                  <th>Candidate</th>
                  <th>Technology</th>
                  <th>Round</th>
                  {!handlerView && !effectiveAttendee && <th>Attendee</th>}
                  <th>Attendance</th>
                  {canManage && <th aria-label="Actions" />}
                </tr>
              </thead>
              <tbody>
                {rows.filter(row => {
                  if (!dashboardStatusFilter) return true
                  const s = resolvedStatus(row)
                  if (dashboardStatusFilter === 'pending') return !s || s === 'pending'
                  return s === dashboardStatusFilter
                }).map(row => {
                  const status = resolvedStatus(row)
                  return (
                    <tr key={row.id} className={`ops-interview-row ops-interview-row--${statusTone(status)}`}>
                      <td data-label="Date" className="ops-interview-date">
                        {formatDayLabel(row.date)}
                      </td>
                      <td data-label="Time" className="ops-interview-time">
                        {[row.time, row.time_end].filter(Boolean).map(formatClockTime).join(' – ') || '—'}
                      </td>
                      <td data-label="Candidate">
                        <strong>{row.name}</strong>
                        {row.phone && <span className="ops-interview-phone">{row.phone}</span>}
                      </td>
                      <td data-label="Technology">{row.technology || '—'}</td>
                      <td data-label="Round">{row.interview_round || '—'}</td>
                      {!handlerView && !effectiveAttendee && (
                        <td data-label="Attendee">{row.interview_attendee_resolved || row.interview_attendee || 'Bhavana'}</td>
                      )}
                      <td data-label="Attendance" className="ops-interview-attendance-cell">
                        <div className="ops-interview-attendance-form">
                          <AttendanceSelect
                            value={status === 'pending' ? '' : status}
                            disabled={busyId === row.id}
                            ariaLabel={`Attendance for ${row.name}`}
                            onChange={async (val) => {
                              if (!val) { saveAttendance(row, val, row.interview_attendee_resolved || row.interview_attendee || 'Bhavana'); return }
                              const label = STATUS_OPTIONS.find(o => o.value === val)?.label || val
                              const ok = await confirm({
                                title: `Mark as "${label}"?`,
                                message: `Update attendance for ${row.name} to "${label}".`,
                                confirmLabel: label,
                                variant: val === 'not_attended' || val === 'cancelled' ? 'danger' : 'default',
                              })
                              if (ok) {
                                saveAttendance(row, val, row.interview_attendee_resolved || row.interview_attendee || 'Bhavana')
                              }
                            }}
                          />
                          <span className={`ops-status-pill ops-status-pill--${statusTone(status)}`}>
                            {statusLabel(status)}
                          </span>
                        </div>
                      </td>
                      {canManage && <td data-label="Actions" className="ops-dash-attend-cell"><RowActions row={row} busy={busyId === row.id} canEditAttendee={canEditAttendee} onEditAttendee={() => setEditing({ row, mode: 'attendee' })} onEditSlot={() => setEditing({ row, mode: 'slot' })} onRemove={removeSlot} /></td>}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
      {editing && <SlotEditModal row={editing.row} mode={editing.mode} busy={busyId === editing.row.id} onClose={() => setEditing(null)} onSave={values => editing.mode === 'attendee' ? saveAttendee(editing.row, values.attendee) : saveSlot(editing.row, values)} />}
    </section>
  )
}
