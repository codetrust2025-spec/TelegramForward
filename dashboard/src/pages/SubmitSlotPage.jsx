import React, { useCallback, useEffect, useMemo, useState } from 'react'
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

  const selected = candidates.find(c => c.name === name)
  const canConfirm = Boolean(name && parsedSlot?.date && parsedSlot?.time && !busy && !parsing)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [cRes, bRes] = await Promise.all([
        fetch(`${API_BASE}/public/slots/candidates`),
        fetch(`${API_BASE}/public/slots/booked`),
      ])
      const cData = await cRes.json()
      const bData = await bRes.json()
      if (cData.status === 'ok') setCandidates(cData.candidates || [])
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
        setError(data.message || 'Could not read the screenshot')
        return
      }
      setParsedSlot(data.slot || null)
      setSuccess('Slot detected from your invite.')
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
    if (!name || !paymentFile) {
      setError('Select your name and a payment screenshot first.')
      return
    }
    setBusy(true)
    setError('')
    setSuccess('')
    try {
      const fd = new FormData()
      fd.append('name', name)
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
    if (!name) {
      setError('Select your name.')
      return
    }
    if (!slotFile) {
      setError('Upload your interview invite screenshot.')
      return
    }
    if (!parsedSlot?.date || !parsedSlot?.time) {
      setError('Could not read date and time — try a clearer screenshot.')
      return
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
      fd.append('name', name)
      fd.append('date', parsedSlot.date)
      fd.append('time', parsedSlot.time)
      if (parsedSlot.time_end) fd.append('time_end', parsedSlot.time_end)
      if (parsedSlot.interview_round) fd.append('interview_round', parsedSlot.interview_round)
      if (parsedSlot.technology) fd.append('technology', parsedSlot.technology)
      if (paymentProofId) fd.append('payment_proof_id', paymentProofId)
      fd.append('file', slotFile)
      const res = await fetch(`${API_BASE}/public/slots/book`, { method: 'POST', body: fd })
      const data = await res.json()
      if (!res.ok) {
        setError(data.payment_due ? (data.message || 'Payment required before booking.') : (data.message || 'Could not book slot'))
        return
      }
      setSuccess('Slot booked successfully.')
      if (slotPreview) URL.revokeObjectURL(slotPreview)
      setSlotFile(null)
      setSlotPreview('')
      setParsedSlot(null)
      setPaymentProofId('')
      await refresh()
    } catch {
      setError('Network error — try again')
    } finally {
      setBusy(false)
    }
  }

  async function submitSessionComplete(ev) {
    ev.preventDefault()
    if (!name || !sessionFile) {
      setError('Select your name and upload the session complete screenshot.')
      return
    }
    setBusy(true)
    setError('')
    setSuccess('')
    try {
      const fd = new FormData()
      fd.append('name', name)
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

  const upcoming = useMemo(() => booked.slice(0, 8), [booked])

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
              <div className="submit-slot-select-wrap">
                <select
                  className="submit-slot-select"
                  value={name}
                  onChange={ev => { setName(ev.target.value); setPaymentProofId('') }}
                  disabled={busy || parsing}
                >
                  <option value="">Choose candidate…</option>
                  {candidates.map(c => (
                    <option key={c.name} value={c.name}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </div>
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

                {error ? <p className="submit-slot-alert submit-slot-alert--error" role="alert">{error}</p> : null}
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
                  className={`submit-slot-cta${name && sessionFile ? ' submit-slot-cta--ready' : ''}`}
                  disabled={busy || !name || !sessionFile}
                >
                  {busy ? <Spinner size={18} /> : 'Submit session proof'}
                </button>
              </form>
            )}

            {upcoming.length > 0 ? (
              <section className="submit-slot-upcoming">
                <h2>Upcoming slots</h2>
                <ul className="submit-slot-upcoming-list">
                  {upcoming.map((s, i) => (
                    <li key={`${s.name}-${s.date}-${s.time}-${i}`} className="submit-slot-upcoming-item">
                      <div className="submit-slot-upcoming-name">{s.name}</div>
                      <div className="submit-slot-upcoming-when">
                        {formatFriendlyDate(s.date?.slice(0, 10))}
                        <span>·</span>
                        {formatFriendlyTime(s.time)}
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
