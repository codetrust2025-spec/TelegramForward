import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Spinner } from '../Loader.jsx'
import { SubmitSlotFileDrop } from './SubmitSlotFileDrop.jsx'

const API_BASE = typeof window !== 'undefined' && window.location.port === '3000'
  ? ''
  : (typeof window !== 'undefined' ? `${window.location.protocol}//${window.location.host}` : '')

function formatFriendlyDate(iso) {
  if (!iso) return ''
  try {
    const d = new Date(`${iso}T12:00:00`)
    return d.toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' })
  } catch {
    return iso
  }
}

function formatFriendlyTime(hhmm) {
  if (!hhmm) return ''
  const [h, m] = hhmm.split(':').map(Number)
  if (Number.isNaN(h)) return hhmm
  const d = new Date()
  d.setHours(h, m || 0, 0, 0)
  return d.toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit', hour12: true })
}

function platformLabel(platform) {
  const map = {
    teams: 'Microsoft Teams',
    zoom: 'Zoom',
    gmail: 'Gmail',
    google_calendar: 'Google Calendar',
    barraiser: 'BarRaiser',
  }
  return map[platform] || platform || ''
}

const ROUND_OPTIONS = ['L1', 'L2', 'L3', 'HR', 'Final round']

function candidateNameKey(value) {
  return String(value || '').trim().toLocaleLowerCase().replace(/[^a-z0-9]/g, '')
}

function dedupeCandidates(rows) {
  const byName = new Map()
  for (const row of rows || []) {
    const name = String(row?.name || '').trim()
    const key = candidateNameKey(name)
    if (!name || !key) continue
    const current = byName.get(key)
    // Prefer a normally-cased name over an all-uppercase duplicate.
    if (!current || (current.name === current.name.toUpperCase() && name !== name.toUpperCase())) {
      byName.set(key, { ...row, name })
    }
  }
  return [...byName.values()].sort((a, b) => a.name.localeCompare(b.name, 'en', { sensitivity: 'base' }))
}

function SlotCandidatePicker({ candidates, value, onChange, disabled }) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef(null)
  const options = useMemo(() => dedupeCandidates(candidates), [candidates])
  const query = value.trim().toLocaleLowerCase()
  const matches = useMemo(
    () => options.filter(candidate => candidate.name.toLocaleLowerCase().includes(query)),
    [options, query],
  )

  useEffect(() => {
    function close(event) {
      if (!rootRef.current?.contains(event.target)) setOpen(false)
    }
    document.addEventListener('pointerdown', close)
    return () => document.removeEventListener('pointerdown', close)
  }, [])

  return (
    <div ref={rootRef} className="submit-slot-picker">
      <input
        className="submit-slot-select submit-slot-name-input"
        value={value}
        onChange={event => { onChange(event.target.value); setOpen(true) }}
        onFocus={() => setOpen(true)}
        placeholder="Choose or type your name"
        disabled={disabled}
        autoComplete="name"
        aria-autocomplete="list"
        aria-expanded={open}
        aria-controls="slot-candidate-options"
      />
      <button
        type="button"
        className="submit-slot-picker__toggle"
        onClick={() => setOpen(current => !current)}
        disabled={disabled}
        aria-label="Show candidate names"
        aria-expanded={open}
      >⌄</button>
      {open && (
        <div id="slot-candidate-options" className="submit-slot-picker__menu" role="listbox">
          {matches.length ? matches.map(candidate => (
            <button
              key={candidateNameKey(candidate.name)}
              type="button"
              role="option"
              aria-selected={candidate.name.toLocaleLowerCase() === query}
              className="submit-slot-picker__option"
              onClick={() => { onChange(candidate.name); setOpen(false) }}
            >{candidate.name}</button>
          )) : <p className="submit-slot-picker__empty">Type a new candidate name to continue.</p>}
        </div>
      )}
    </div>
  )
}

export function SubmitSlotPage() {
  const [tab, setTab] = useState('book')
  const [candidates, setCandidates] = useState([])
  const [booked, setBooked] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [parsing, setParsing] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const [name, setName] = useState('')
  const [parsedSlot, setParsedSlot] = useState(null)
  const [slotFile, setSlotFile] = useState(null)
  const [slotPreview, setSlotPreview] = useState('')
  const [paymentProofId, setPaymentProofId] = useState('')
  const [paymentFile, setPaymentFile] = useState(null)
  const [sessionFile, setSessionFile] = useState(null)
  const [sessionPreview, setSessionPreview] = useState('')
  const [manualDate, setManualDate] = useState('')
  const [manualTime, setManualTime] = useState('')
  const [interviewRound, setInterviewRound] = useState('')

  const effectiveName = name.trim()
  const selected = useMemo(() => {
    if (!effectiveName) return null
    const key = effectiveName.toLowerCase()
    return dedupeCandidates(candidates).find(c => c.name.toLowerCase() === key) || null
  }, [effectiveName, candidates])
  const bookingSlot = useMemo(() => {
    if (parsedSlot?.date && parsedSlot?.time) return parsedSlot
    if (manualDate && manualTime) {
      return {
        ...parsedSlot,
        date: manualDate,
        time: manualTime,
        time_end: parsedSlot?.time_end || '',
        interview_round: interviewRound || parsedSlot?.interview_round || '',
      }
    }
    return parsedSlot ? { ...parsedSlot, interview_round: interviewRound || parsedSlot.interview_round || '' } : null
  }, [parsedSlot, manualDate, manualTime, interviewRound])
  const canConfirm = Boolean(
    effectiveName && slotFile && interviewRound && !busy && !parsing,
  )
  const showManualSlotFields = Boolean(
    slotFile && !parsing && (!parsedSlot?.date || !parsedSlot?.time),
  )

  const refresh = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [cRes, bRes] = await Promise.all([
        fetch(`${API_BASE}/public/slots/candidates`, { cache: 'no-store' }),
        fetch(`${API_BASE}/public/slots/booked`, { cache: 'no-store' }),
      ])
      const cData = await cRes.json()
      const bData = await bRes.json()
      if (cData.status === 'ok') setCandidates(dedupeCandidates(cData.candidates || []))
      if (bData.status === 'ok') setBooked(bData.slots || [])
    } catch {
      setError('Could not load — check your connection and try again.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  useEffect(() => () => {
    if (slotPreview) URL.revokeObjectURL(slotPreview)
    if (sessionPreview) URL.revokeObjectURL(sessionPreview)
  }, [slotPreview, sessionPreview])

  async function parseScreenshot(file) {
    if (!file) {
      setParsedSlot(null)
      return
    }
    setParsing(true)
    setError('')
    setSuccess('')
    try {
      const fd = new FormData()
      fd.append('file', file)
      const res = await fetch(`${API_BASE}/public/slots/parse-screenshot`, { method: 'POST', body: fd })
      const data = await res.json()
      if (!res.ok) {
        setParsedSlot(null)
        setError('Auto-read failed — enter date & time below or upload a clearer screenshot.')
        return
      }
      setParsedSlot(data.slot || null)
      setInterviewRound(data.slot?.interview_round || '')
      setManualDate('')
      setManualTime('')
      setSuccess('Date & time detected — tap Confirm slot below to save.')
    } catch {
      setParsedSlot(null)
      setError('Network error while reading screenshot')
    } finally {
      setParsing(false)
    }
  }

  async function onSlotFileChange(file) {
    if (slotPreview) URL.revokeObjectURL(slotPreview)
    setSlotFile(file || null)
    setParsedSlot(null)
    setManualDate('')
    setManualTime('')
    setInterviewRound('')
    setSuccess('')
    if (file) {
      setSlotPreview(URL.createObjectURL(file))
      await parseScreenshot(file)
    } else {
      setSlotPreview('')
    }
  }

  async function onSessionFileChange(file) {
    if (sessionPreview) URL.revokeObjectURL(sessionPreview)
    setSessionFile(file || null)
    if (file) setSessionPreview(URL.createObjectURL(file))
    else setSessionPreview('')
  }

  async function uploadPaymentProof() {
    if (!effectiveName || !paymentFile) {
      setError('Enter your name and attach a payment screenshot first.')
      return
    }
    setBusy(true)
    setError('')
    setSuccess('')
    try {
      const fd = new FormData()
      fd.append('name', effectiveName)
      fd.append('file', paymentFile)
      const res = await fetch(`${API_BASE}/public/slots/payment-proof`, { method: 'POST', body: fd })
      const data = await res.json()
      if (!res.ok) {
        setError(data.message || 'Payment upload failed')
        return
      }
      setPaymentProofId(data.proof_id || '')
      setPaymentFile(null)
      setSuccess('Payment proof saved — you can confirm your slot.')
    } catch {
      setError('Network error — try again')
    } finally {
      setBusy(false)
    }
  }

  async function submitBook(ev) {
    ev.preventDefault()
    if (!effectiveName) {
      setError('Enter your name.')
      return
    }
    if (!slotFile) {
      setError('Upload your interview invite screenshot.')
      return
    }
    if (!bookingSlot?.date || !bookingSlot?.time) {
      // Server re-parses screenshot on book when date/time omitted
    }
    if (selected?.needs_payment_proof && !paymentProofId) {
      setError(`Upload payment proof first (₹${(selected.balance_due || 0).toLocaleString('en-IN')} due).`)
      return
    }
    setBusy(true)
    setError('')
    setSuccess('')
    try {
      const fd = new FormData()
      fd.append('name', effectiveName)
      if (bookingSlot?.date) fd.append('date', bookingSlot.date)
      if (bookingSlot?.time) fd.append('time', bookingSlot.time)
      if (bookingSlot?.time_end) fd.append('time_end', bookingSlot.time_end)
      if (bookingSlot?.interview_round) fd.append('interview_round', bookingSlot.interview_round)
      if (bookingSlot?.technology) fd.append('technology', bookingSlot.technology)
      if (paymentProofId) fd.append('payment_proof_id', paymentProofId)
      fd.append('file', slotFile)
      const res = await fetch(`${API_BASE}/public/slots/book`, { method: 'POST', body: fd })
      const data = await res.json()
      if (!res.ok) {
        setError(data.payment_due ? (data.message || 'Payment required before booking.') : (data.message || 'Could not book slot'))
        return
      }
      if (slotPreview) URL.revokeObjectURL(slotPreview)
      setSlotFile(null)
      setSlotPreview('')
      setParsedSlot(null)
      setManualDate('')
      setManualTime('')
      setInterviewRound('')
      setPaymentProofId('')
      setSuccess(`Slot confirmed for ${data.candidate?.name || effectiveName}.`)
      await refresh()
    } catch {
      setError('Network error — try again')
    } finally {
      setBusy(false)
    }
  }

  async function submitSessionComplete(ev) {
    ev.preventDefault()
    if (!effectiveName || !sessionFile) {
      setError('Enter your name and upload the session complete screenshot.')
      return
    }
    setBusy(true)
    setError('')
    setSuccess('')
    try {
      const fd = new FormData()
      fd.append('name', effectiveName)
      fd.append('file', sessionFile)
      const res = await fetch(`${API_BASE}/public/slots/session-complete`, { method: 'POST', body: fd })
      const data = await res.json()
      if (!res.ok) {
        setError(data.message || 'Upload failed')
        return
      }
      setSuccess('Session marked complete — thank you.')
      if (sessionPreview) URL.revokeObjectURL(sessionPreview)
      setSessionFile(null)
      setSessionPreview('')
    } catch {
      setError('Network error — try again')
    } finally {
      setBusy(false)
    }
  }

  // The selected candidate's just-confirmed slot should not look like it is
  // still waiting in the booking queue.  Keep the list as awareness of other
  // confirmed appointments only.
  const upcoming = useMemo(
    () => booked
      .filter(slot => candidateNameKey(slot.name) !== candidateNameKey(effectiveName))
      .slice(0, 8),
    [booked, effectiveName],
  )

  return (
    <div className="auth-screen submit-slot-screen">
      <div className="submit-slot-glow" aria-hidden="true" />
      <div className="auth-card submit-slot-card">
        <header className="submit-slot-hero">
          <div className="submit-slot-hero-icon" aria-hidden="true">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
              <rect x="3" y="4" width="18" height="18" rx="3" />
              <path d="M16 2v4M8 2v4M3 10h18" strokeLinecap="round" />
            </svg>
          </div>
          <div>
            <h1>Interview slots</h1>
            <p>Upload your invite — we read the date and time for you.</p>
          </div>
        </header>

        <div className="submit-slot-tabs" role="tablist" aria-label="Slot actions">
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'book'}
            className={tab === 'book' ? 'submit-slot-tab submit-slot-tab--active' : 'submit-slot-tab'}
            onClick={() => { setTab('book'); setError(''); setSuccess('') }}
          >
            Book slot
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'session'}
            className={tab === 'session' ? 'submit-slot-tab submit-slot-tab--active' : 'submit-slot-tab'}
            onClick={() => { setTab('session'); setError(''); setSuccess('') }}
          >
            Session complete
          </button>
        </div>

        {loading ? (
          <div className="submit-slot-loading"><Spinner size={28} /></div>
        ) : (
          <div className="submit-slot-body">
            <label className="submit-slot-field">
              <span className="submit-slot-field-label">Your name</span>
              <SlotCandidatePicker
                candidates={candidates}
                value={name}
                onChange={value => { setName(value); setPaymentProofId('') }}
                disabled={busy || parsing}
              />
              <span className="submit-slot-field-hint">
                Pick from the list or type a new client name.
              </span>
            </label>

            {tab === 'book' ? (
              <form className="submit-slot-form" onSubmit={submitBook}>
                {selected?.needs_payment_proof ? (
                  <div className="submit-slot-pay-card">
                    <div className="submit-slot-pay-head">
                      <span>Payment due</span>
                      <strong>₹{(selected.balance_due || 0).toLocaleString('en-IN')}</strong>
                    </div>
                    {paymentProofId ? (
                      <p className="submit-slot-pay-ok">Payment proof on file</p>
                    ) : (
                      <>
                        <SubmitSlotFileDrop
                          compact
                          label="Payment screenshot"
                          file={paymentFile}
                          disabled={busy || parsing}
                          busy={busy}
                          onFile={setPaymentFile}
                        />
                        <button
                          type="button"
                          className="submit-slot-secondary-btn"
                          disabled={busy || parsing || !paymentFile}
                          onClick={uploadPaymentProof}
                        >
                          Save payment proof
                        </button>
                      </>
                    )}
                  </div>
                ) : null}

                <SubmitSlotFileDrop
                  label="Interview invite screenshot"
                  hint="Teams, Gmail, Calendar, or Zoom — date and time must be visible."
                  file={slotFile}
                  previewUrl={slotPreview}
                  disabled={busy}
                  busy={parsing}
                  onFile={onSlotFileChange}
                />

                <label className="submit-slot-field">
                  <span className="submit-slot-field-label">Interview round</span>
                  <div className="submit-slot-select-wrap">
                    <select
                      className="submit-slot-select"
                      value={interviewRound}
                      onChange={event => setInterviewRound(event.target.value)}
                      disabled={busy || parsing}
                      required
                    >
                      <option value="">Select round (L1, L2…)</option>
                      {ROUND_OPTIONS.map(round => <option key={round} value={round}>{round}</option>)}
                    </select>
                  </div>
                </label>

                {parsing ? (
                  <div className="submit-slot-status submit-slot-status--loading">
                    <Spinner size={18} />
                    <span>Reading your invite…</span>
                  </div>
                ) : null}

                {parsedSlot?.date && parsedSlot?.time ? (
                  <div className="submit-slot-detected">
                    <div className="submit-slot-detected-badge">Detected</div>
                    <div className="submit-slot-detected-main">
                      <span className="submit-slot-detected-date">{formatFriendlyDate(parsedSlot.date)}</span>
                      <span className="submit-slot-detected-time">
                        {formatFriendlyTime(parsedSlot.time)}
                        {parsedSlot.time_end ? ` – ${formatFriendlyTime(parsedSlot.time_end)}` : ''}
                      </span>
                    </div>
                    <div className="submit-slot-detected-meta">
                      {parsedSlot.interview_round ? <span className="submit-slot-chip">{parsedSlot.interview_round}</span> : null}
                      {parsedSlot.technology ? <span className="submit-slot-chip submit-slot-chip--muted">{parsedSlot.technology}</span> : null}
                      {parsedSlot.platform ? <span className="submit-slot-chip submit-slot-chip--muted">{platformLabel(parsedSlot.platform)}</span> : null}
                    </div>
                  </div>
                ) : null}

                {showManualSlotFields ? (
                  <div className="submit-slot-manual">
                    <p className="submit-slot-manual-hint">
                      Include the date line in your screenshot (e.g. Sat, Jun 20, 2:00 PM), or enter date &amp; time manually.
                    </p>
                    <div className="submit-slot-manual-grid">
                      <label className="submit-slot-field">
                        <span className="submit-slot-field-label">Interview date</span>
                        <input
                          className="submit-slot-select submit-slot-name-input"
                          type="date"
                          value={manualDate}
                          onChange={ev => setManualDate(ev.target.value)}
                          disabled={busy || parsing}
                        />
                      </label>
                      <label className="submit-slot-field">
                        <span className="submit-slot-field-label">Start time</span>
                        <input
                          className="submit-slot-select submit-slot-name-input"
                          type="time"
                          value={manualTime}
                          onChange={ev => setManualTime(ev.target.value)}
                          disabled={busy || parsing}
                        />
                      </label>
                    </div>
                  </div>
                ) : null}

                {error && !showManualSlotFields ? (
                  <p className="submit-slot-alert submit-slot-alert--error" role="alert">{error}</p>
                ) : null}
                {success ? <p className="submit-slot-alert submit-slot-alert--success">{success}</p> : null}

                <button
                  type="submit"
                  className={`submit-slot-cta${canConfirm ? ' submit-slot-cta--ready' : ''}`}
                  disabled={!canConfirm}
                >
                  {busy ? <Spinner size={18} /> : 'Confirm slot'}
                </button>
              </form>
            ) : (
              <form className="submit-slot-form" onSubmit={submitSessionComplete}>
                <p className="submit-slot-lead">Upload the &quot;Session complete&quot; screen after your interview ends.</p>
                <SubmitSlotFileDrop
                  label="Session complete screenshot"
                  file={sessionFile}
                  previewUrl={sessionPreview}
                  disabled={busy}
                  onFile={onSessionFileChange}
                />
                {error ? <p className="submit-slot-alert submit-slot-alert--error" role="alert">{error}</p> : null}
                {success ? <p className="submit-slot-alert submit-slot-alert--success">{success}</p> : null}
                <button
                  type="submit"
                  className={`submit-slot-cta${name.trim() && sessionFile ? ' submit-slot-cta--ready' : ''}`}
                  disabled={busy || !name.trim() || !sessionFile}
                >
                  {busy ? <Spinner size={18} /> : 'Submit session proof'}
                </button>
              </form>
            )}

            {upcoming.length > 0 ? (
              <section className="submit-slot-upcoming">
                <h2>Other confirmed upcoming slots</h2>
                <ul className="submit-slot-upcoming-list">
                  {upcoming.map((s, i) => (
                    <li key={`${s.name}-${s.date}-${s.time}-${i}`} className="submit-slot-upcoming-item">
                      <div className="submit-slot-upcoming-name">{s.name}</div>
                      <div className="submit-slot-upcoming-when">
                        {formatFriendlyDate(s.date?.slice(0, 10))}
                        <span>·</span>
                        {formatFriendlyTime(s.time)}
                        {s.time_end ? ` – ${formatFriendlyTime(s.time_end)}` : ''}
                      </div>
                      {s.interview_round ? (
                        <span className="submit-slot-upcoming-round">{s.interview_round}</span>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
          </div>
        )}
      </div>
      <p className="submit-slot-foot">TeleAutomation · secure slot booking</p>
    </div>
  )
}
