import React, { useEffect, useMemo, useRef, useState } from 'react'

const HOURS = Array.from({ length: 12 }, (_, index) => index + 1)
const MINUTES = Array.from({ length: 12 }, (_, index) => index * 5)

function parseTime(value) {
  const raw = String(value || '').trim()
  const twelveHour = raw.match(/^(\d{1,2}):(\d{2})\s*(AM|PM)$/i)
  if (twelveHour) {
    return {
      hasValue: true,
      hour: Math.min(12, Math.max(1, Number(twelveHour[1]) || 12)),
      minute: Math.min(59, Math.max(0, Number(twelveHour[2]) || 0)),
      period: twelveHour[3].toUpperCase(),
    }
  }

  const twentyFourHour = raw.match(/^(\d{1,2}):(\d{2})$/)
  if (twentyFourHour) {
    const hour24 = Math.min(23, Math.max(0, Number(twentyFourHour[1]) || 0))
    return {
      hasValue: true,
      hour: hour24 % 12 || 12,
      minute: Math.min(59, Math.max(0, Number(twentyFourHour[2]) || 0)),
      period: hour24 >= 12 ? 'PM' : 'AM',
    }
  }

  return { hasValue: false, hour: 12, minute: 0, period: 'AM' }
}

function formatTime({ hour, minute, period }) {
  return `${hour}:${String(minute).padStart(2, '0')} ${period}`
}

function formatStoredTime({ hour, minute, period }) {
  return `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')} ${period}`
}

export const TwelveHourTimePicker = React.forwardRef(function TwelveHourTimePicker(
  { value, onChange, disabled = false },
  triggerRef,
) {
  const parsed = useMemo(() => parseTime(value), [value])
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState('hour')
  const [draft, setDraft] = useState(parsed)
  const rootRef = useRef(null)

  useEffect(() => { setDraft(parsed) }, [parsed])

  useEffect(() => {
    if (!open) return undefined
    function closeOnOutsideClick(event) {
      if (!rootRef.current?.contains(event.target)) setOpen(false)
    }
    function closeOnEscape(event) {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', closeOnOutsideClick)
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.removeEventListener('mousedown', closeOnOutsideClick)
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [open])

  const minuteOptions = useMemo(() => {
    if (MINUTES.includes(draft.minute)) return MINUTES
    return [...MINUTES, draft.minute].sort((left, right) => left - right)
  }, [draft.minute])

  function commit(next) {
    const selected = { ...next, hasValue: true }
    setDraft(selected)
    onChange?.(formatStoredTime(selected))
  }

  function selectHour(hour) {
    commit({ ...draft, hour })
    setMode('minute')
  }

  const selectedLabel = parsed.hasValue ? formatTime(parsed) : 'Choose time'
  const draftLabel = formatTime(draft)

  return (
    <div className={`sbs-time12${open ? ' sbs-time12--open' : ''}`} ref={rootRef}>
      <button
        ref={triggerRef}
        type="button"
        className="sbs-time12__trigger"
        aria-label={`Start time: ${selectedLabel}`}
        aria-expanded={open}
        aria-haspopup="dialog"
        disabled={disabled}
        onClick={() => {
          setOpen(current => !current)
          setMode('hour')
        }}
      >
        <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
          <circle cx="12" cy="12" r="9" />
          <path d="M12 7v5l3 2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <span className={parsed.hasValue ? '' : 'sbs-time12__placeholder'}>{selectedLabel}</span>
        <svg aria-hidden="true" className="sbs-time12__chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>

      {open && (
        <div className="sbs-time12__panel" role="dialog" aria-label="Choose start time">
          <div className="sbs-time12__top">
            <strong className="sbs-time12__display" aria-live="polite">{draftLabel}</strong>
            <div className="sbs-time12__period" role="group" aria-label="Select AM or PM">
              {['AM', 'PM'].map(period => (
                <button
                  key={period}
                  type="button"
                  className={draft.period === period ? 'sbs-time12__period-btn sbs-time12__period-btn--active' : 'sbs-time12__period-btn'}
                  aria-pressed={draft.period === period}
                  onClick={() => commit({ ...draft, period })}
                >
                  {period}
                </button>
              ))}
            </div>
          </div>

          <div className="sbs-time12__modes" role="tablist" aria-label="Choose hour or minutes">
            <button type="button" role="tab" aria-selected={mode === 'hour'} className={mode === 'hour' ? 'sbs-time12__mode sbs-time12__mode--active' : 'sbs-time12__mode'} onClick={() => setMode('hour')}>Hour</button>
            <button type="button" role="tab" aria-selected={mode === 'minute'} className={mode === 'minute' ? 'sbs-time12__mode sbs-time12__mode--active' : 'sbs-time12__mode'} onClick={() => setMode('minute')}>Minute</button>
          </div>

          <div className="sbs-time12__options" role="group" aria-label={mode === 'hour' ? 'Select hour' : 'Select minutes'}>
            {(mode === 'hour' ? HOURS : minuteOptions).map(option => {
              const selected = mode === 'hour' ? draft.hour === option : draft.minute === option
              const label = mode === 'hour' ? String(option) : String(option).padStart(2, '0')
              return (
                <button
                  key={`${mode}-${option}`}
                  type="button"
                  className={selected ? 'sbs-time12__option sbs-time12__option--active' : 'sbs-time12__option'}
                  aria-label={mode === 'hour' ? `${option} hour` : `${label} minutes`}
                  aria-pressed={selected}
                  onClick={() => mode === 'hour' ? selectHour(option) : commit({ ...draft, minute: option })}
                >
                  {label}
                </button>
              )
            })}
          </div>

          <div className="sbs-time12__footer">
            <span>12-hour format</span>
            <button type="button" className="sbs-time12__done" onClick={() => setOpen(false)}>Done</button>
          </div>
        </div>
      )}
    </div>
  )
})
