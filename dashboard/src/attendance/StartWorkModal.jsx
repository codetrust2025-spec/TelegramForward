/**
 * The once-a-day Start Work prompt.
 *
 * Mounted globally, so it appears on the first dashboard open of the day
 * whatever page that happens to be. Whether it appears at all is decided by the
 * server — configuration, enrolment, the IST day, and whether a record already
 * exists — so a reload or a second tab cannot resurrect a prompt that has
 * already been answered.
 *
 * "Once per day" is taken literally: dismissing it without starting also
 * suppresses it until the next IST day. That is deliberate, and it is why a
 * dismissed day has to be recoverable through the admin override rather than by
 * nagging the employee.
 */

import { useCallback, useEffect, useState } from 'react'
import { useAuth } from '../context/AuthContext.jsx'
import { useDialogA11y } from '../hooks/useDialogA11y.js'
import { fetchToday, startWork } from './attendanceApi.js'

const DISMISS_KEY = 'attendance_prompt_dismissed'

function dismissedKey(employeeId, date) {
  return `${DISMISS_KEY}:${employeeId}:${date}`
}

function wasDismissedToday(employeeId, date) {
  if (!employeeId || !date) return false
  try {
    return localStorage.getItem(dismissedKey(employeeId, date)) === '1'
  } catch {
    return false
  }
}

function rememberDismissal(employeeId, date) {
  try {
    localStorage.setItem(dismissedKey(employeeId, date), '1')
  } catch {
    /* private mode — the prompt simply reappears on the next load */
  }
}

export function StartWorkModal() {
  const { authenticated } = useAuth()
  const [today, setToday] = useState(null)
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const close = useCallback(() => {
    if (today?.employee_id && today?.date) rememberDismissal(today.employee_id, today.date)
    setOpen(false)
  }, [today])

  const dialogRef = useDialogA11y(open, close)

  useEffect(() => {
    if (!authenticated) {
      setOpen(false)
      return undefined
    }
    let cancelled = false
    fetchToday()
      .then((data) => {
        if (cancelled) return
        setToday(data)
        if (data.prompt && !wasDismissedToday(data.employee_id, data.date)) setOpen(true)
      })
      .catch(() => {
        /* attendance must never block the dashboard from loading */
      })
    return () => {
      cancelled = true
    }
  }, [authenticated])

  const onStart = async () => {
    setBusy(true)
    setError('')
    try {
      const result = await startWork()
      setToday((prev) => ({ ...(prev || {}), already_recorded: true, record: result.record }))
      setOpen(false)
    } catch (err) {
      // 403 here is the off-network case; the server owns that decision.
      setError(err.detail || err.message || 'Could not record attendance.')
    } finally {
      setBusy(false)
    }
  }

  if (!open || !today) return null

  const name = today.display_name || 'there'
  const blocked = !today.can_start
  const networkMessage = today.network?.message

  return (
    <div className="attendance-modal-backdrop">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="attendance-modal-title"
        className="attendance-modal"
      >
        <h2 id="attendance-modal-title" className="attendance-modal-title">
          Good morning, {name}
        </h2>
        <p className="attendance-modal-body">Ready to start your work day?</p>

        <dl className="attendance-modal-facts">
          <div>
            <dt>Date</dt>
            <dd>{today.date}</dd>
          </div>
          <div>
            <dt>Shift starts</dt>
            <dd>{today.shift_start}</dd>
          </div>
        </dl>

        {blocked && (networkMessage || error) && (
          <p className="attendance-modal-error" role="alert">
            {error || networkMessage}
          </p>
        )}
        {!blocked && error && (
          <p className="attendance-modal-error" role="alert">
            {error}
          </p>
        )}

        <div className="attendance-modal-actions">
          <button type="button" className="attendance-modal-secondary" onClick={close}>
            Not now
          </button>
          <button
            type="button"
            className="attendance-modal-primary"
            onClick={onStart}
            disabled={blocked || busy}
            title={blocked ? networkMessage || 'Attendance cannot be started right now' : undefined}
          >
            {busy ? 'Recording…' : 'Start Work'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default StartWorkModal
