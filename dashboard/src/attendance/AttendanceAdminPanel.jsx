/**
 * HR view: attendance records, monthly percentages, overrides and the calendar.
 *
 * Shows the working, not just the answer. A percentage that says "82%" without
 * the days behind it is not auditable, and this number is meant to inform pay,
 * so every figure here is presented with its numerator and denominator.
 *
 * Contains no salary and no commission. Attendance-linked payout is a separate,
 * undecided policy.
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  fetchConfig,
  fetchRecords,
  fetchSummary,
  overrideDay,
  saveConfig,
} from './attendanceApi.js'

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

function currentMonth() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

function StateBadge({ state }) {
  return <span className={`attendance-state attendance-state--${state}`}>{state.replace('_', ' ')}</span>
}

export default function AttendanceAdminPanel() {
  const [month, setMonth] = useState(currentMonth())
  const [summary, setSummary] = useState(null)
  const [records, setRecords] = useState([])
  const [config, setConfig] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    setBusy(true)
    setError('')
    try {
      const [summaryBody, recordsBody, configBody] = await Promise.all([
        fetchSummary(month),
        fetchRecords(month),
        fetchConfig(),
      ])
      setSummary(summaryBody.summary)
      setRecords(recordsBody.records || [])
      setConfig(configBody.config)
    } catch (err) {
      setError(err.detail || err.message || 'Could not load attendance')
    } finally {
      setBusy(false)
    }
  }, [month])

  useEffect(() => {
    load()
  }, [load])

  const recordsByEmployee = useMemo(() => {
    const map = new Map()
    for (const row of records) {
      if (!map.has(row.employee_id)) map.set(row.employee_id, [])
      map.get(row.employee_id).push(row)
    }
    return map
  }, [records])

  const runOverride = async (employeeId) => {
    const date = window.prompt('Override which date? (YYYY-MM-DD)')
    if (!date) return
    const reason = window.prompt('Reason for the override (recorded in the audit trail)')
    if (!reason) return
    try {
      await overrideDay({ employee_id: employeeId, date, reason })
      await load()
    } catch (err) {
      setError(err.detail || err.message || 'Override failed')
    }
  }

  const toggleWeekday = async (index) => {
    if (!config) return
    const next = config.working_weekdays.includes(index)
      ? config.working_weekdays.filter((day) => day !== index)
      : [...config.working_weekdays, index].sort()
    try {
      const body = await saveConfig({ working_weekdays: next })
      setConfig(body.config)
      await load()
    } catch (err) {
      setError(err.detail || err.message || 'Could not save the calendar')
    }
  }

  return (
    <section className="attendance-panel">
      <header className="attendance-panel-header">
        <h2>Attendance</h2>
        <label>
          Month{' '}
          <input type="month" value={month} onChange={(e) => setMonth(e.target.value || currentMonth())} />
        </label>
        <button type="button" onClick={load} disabled={busy}>
          {busy ? 'Loading…' : 'Refresh'}
        </button>
      </header>

      {error && <p className="attendance-error" role="alert">{error}</p>}

      {config && !config.configured && (
        <p className="attendance-warning" role="alert">
          No working calendar is configured, so attendance is not being measured and the
          Start Work prompt is hidden. Choose the working weekdays below to begin.
        </p>
      )}

      {config && (
        <div className="attendance-config">
          <h3>Working calendar</h3>
          <div className="attendance-weekdays">
            {WEEKDAYS.map((label, index) => (
              <label key={label} className="attendance-weekday">
                <input
                  type="checkbox"
                  checked={config.working_weekdays.includes(index)}
                  onChange={() => toggleWeekday(index)}
                />
                {label}
              </label>
            ))}
          </div>
          <p className="attendance-config-note">
            Shift starts {config.shift_start}, {config.grace_minutes} minutes grace.
            Counting toward attendance: {config.credited_states.join(', ')}.
            {config.holidays.length > 0 && ` Holidays: ${config.holidays.join(', ')}.`}
            {config.office_ip_allowlist.length === 0
              && ' No office IP is allowlisted yet, so Start Work stays blocked for everyone.'}
          </p>
        </div>
      )}

      {summary && (
        <>
          <p className="attendance-denominator">
            {summary.scheduled_working_days} scheduled working days up to {summary.scheduled_through}.
            Percentages are measured against elapsed days only.
          </p>
          <table className="attendance-table">
            <thead>
              <tr>
                <th>Employee</th>
                <th>ID</th>
                <th>Credited</th>
                <th>Recorded</th>
                <th>Absent</th>
                <th>Late</th>
                <th>Overrides</th>
                <th>Attendance</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {summary.employees.map((row) => (
                <tr key={row.employee_id}>
                  <td>{row.display_name || '—'}</td>
                  <td className="attendance-id">{row.employee_id}</td>
                  <td>
                    {row.days_credited} / {row.scheduled_working_days}
                  </td>
                  <td>{row.days_recorded}</td>
                  <td>{row.days_absent}</td>
                  <td>{row.by_state.late}</td>
                  <td>{row.overrides}</td>
                  <td className="attendance-percentage">{row.attendance_percentage}%</td>
                  <td>
                    <button type="button" onClick={() => runOverride(row.employee_id)}>
                      Override a day
                    </button>
                  </td>
                </tr>
              ))}
              {summary.employees.length === 0 && (
                <tr>
                  <td colSpan={9}>No employees are enrolled for attendance yet.</td>
                </tr>
              )}
            </tbody>
          </table>
        </>
      )}

      <h3>Records</h3>
      <table className="attendance-table">
        <thead>
          <tr>
            <th>Date</th>
            <th>Employee</th>
            <th>Started</th>
            <th>State</th>
            <th>Network</th>
            <th>Override</th>
          </tr>
        </thead>
        <tbody>
          {records.map((row) => (
            <tr key={`${row.employee_id}:${row.date}`}>
              <td>{row.date}</td>
              <td className="attendance-id">{row.employee_id}</td>
              <td>{String(row.started_at).slice(11, 16)}</td>
              <td><StateBadge state={row.state} /></td>
              <td>
                {row.network?.verified
                  ? `office · ${row.network.ip}`
                  : `unverified${row.network?.ip ? ` · ${row.network.ip}` : ''}`}
              </td>
              <td>
                {row.override
                  ? `${row.override.approved_by}: ${row.override.reason}`
                  : '—'}
              </td>
            </tr>
          ))}
          {records.length === 0 && (
            <tr>
              <td colSpan={6}>No attendance recorded in this month.</td>
            </tr>
          )}
        </tbody>
      </table>

      <p className="attendance-footnote">
        Attendance percentages are reported here only. They are not applied to salary or
        commission: that policy is still open, and the commission source-of-truth
        discrepancy has to be settled first.
      </p>
    </section>
  )
}

export { AttendanceAdminPanel }
