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
  } catch { return iso }
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
  const map = { teams: 'Microsoft Teams', zoom: 'Zoom', gmail: 'Gmail', google_calendar: 'Google Calendar', barraiser: 'BarRaiser' }
  return map[platform] || platform || ''
}

const ROUND_OPTIONS = ['L1', 'L2', 'L3', 'HR', 'Final round', 'Screening']

function candidateNameKey(value) {
  return String(value || '').trim().toLocaleLowerCase().replace(/[^a-z0-9]/g, '')
}

function formatDayHeader(iso) {
  if (!iso) return ''
  try {
    const d = new Date(`${iso}T12:00:00`)
    const today = new Date()
    const tomorrow = new Date(); tomorrow.setDate(today.getDate() + 1)
    if (d.toDateString() === today.toDateString()) return 'Today'
    if (d.toDateString() === tomorrow.toDateString()) return 'Tomorrow'
    return d.toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'short', year: 'numeric' })
  } catch { return iso }
}

function groupSlotsByDate(slots) {
  const groups = new Map()
  for (const slot of slots) {
    const key = (slot.date || '').slice(0, 10)
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key).push(slot)
  }
  return [...groups.entries()].map(([date, items]) => ({ date, items }))
}

function dedupeCandidates(rows) {
  const byName = new Map()
  for (const row of rows || []) {
    const name = String(row?.name || '').trim()
    const key = candidateNameKey(name)
    if (!name || !key) continue
    const current = byName.get(key)
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
    () => options.filter(c => c.name.toLocaleLowerCase().includes(query)),
    [options, query],
  )
  useEffect(() => {
    function close(e) { if (!rootRef.current?.contains(e.target)) setOpen(false) }
    document.addEventListener('pointerdown', close)
    return () => document.removeEventListener('pointerdown', close)
  }, [])
  return (
    <div ref={rootRef} className="sbs-picker">
      <div className="sbs-picker__input-wrap">
        <svg className="sbs-picker__icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/>
        </svg>
        <input
          className="sbs-input sbs-name-input"
          value={value}
          onChange={e => { onChange(e.target.value); setOpen(true) }}
          onFocus={() => setOpen(true)}
          placeholder="Choose or type your name"
          disabled={disabled}
          autoComplete="name"
          aria-autocomplete="list"
          aria-expanded={open}
          aria-controls="sbs-candidate-options"
        />
        <button type="button" className="sbs-picker__toggle" onClick={() => setOpen(v => !v)} disabled={disabled} aria-label="Show names" aria-expanded={open}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M6 9l6 6 6-6"/></svg>
        </button>
      </div>
      {open && (
        <div id="sbs-candidate-options" className="sbs-picker__menu" role="listbox">
          {matches.length ? matches.map(c => (
            <button key={candidateNameKey(c.name)} type="button" role="option"
              aria-selected={c.name.toLocaleLowerCase() === query}
              className="sbs-picker__option"
              onClick={() => { onChange(c.name); setOpen(false) }}
            >{c.name}</button>
          )) : <p className="sbs-picker__empty">Type a new name to continue.</p>}
        </div>
      )}
    </div>
  )
}

// Calendar icon for slot cards
function CalIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
      <rect x="3" y="4" width="18" height="18" rx="3"/>
      <path d="M16 2v4M8 2v4M3 10h18" strokeLinecap="round"/>
    </svg>
  )
}

function SlotCard({ slot, index, selected, onClick }) {
  const isFirst = index === 0
  return (
    <button
      type="button"
      className={`sbs-slot-card${selected ? ' sbs-slot-card--selected' : ''}`}
      onClick={onClick}
    >
      <div className={`sbs-slot-card__icon${selected ? ' sbs-slot-card__icon--active' : ''}`}>
        <CalIcon />
      </div>
      <div className="sbs-slot-card__body">
        <div className="sbs-slot-card__name-row">
          <span className="sbs-slot-card__name">{slot.name}</span>
          {isFirst && <span className="sbs-slot-card__recommended"><span className="sbs-slot-card__star">★</span> Recommended</span>}
        </div>
        <div className="sbs-slot-card__date">{formatFriendlyDate(slot.date?.slice(0, 10))}</div>
        <div className="sbs-slot-card__time">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2" strokeLinecap="round"/></svg>
          <span>{formatFriendlyTime(slot.time)}{slot.time_end ? ` – ${formatFriendlyTime(slot.time_end)}` : ''}</span>
        </div>
      </div>
      {slot.interview_round && (
        <span className="sbs-slot-card__round">{slot.interview_round}</span>
      )}
      <svg className="sbs-slot-card__arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 18l6-6-6-6"/></svg>
    </button>
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
  const [showUploadMode, setShowUploadMode] = useState(false)

  const effectiveName = name.trim()
  const selected = useMemo(() => {
    if (!effectiveName) return null
    const key = effectiveName.toLowerCase()
    return dedupeCandidates(candidates).find(c => c.name.toLowerCase() === key) || null
  }, [effectiveName, candidates])

  const bookingSlot = useMemo(() => {
    if (parsedSlot?.date && parsedSlot?.time) return { ...parsedSlot, interview_round: interviewRound || parsedSlot.interview_round || '' }
    if (manualDate && manualTime) return { ...parsedSlot, date: manualDate, time: manualTime, time_end: parsedSlot?.time_end || '', interview_round: interviewRound || parsedSlot?.interview_round || '' }
    return parsedSlot ? { ...parsedSlot, interview_round: interviewRound || parsedSlot.interview_round || '' } : null
  }, [parsedSlot, manualDate, manualTime, interviewRound])

  const canConfirm = Boolean(effectiveName && slotFile && interviewRound && !busy && !parsing)
  const showManualSlotFields = Boolean(slotFile && !parsing && (!parsedSlot?.date || !parsedSlot?.time))

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const [cRes, bRes] = await Promise.all([
        fetch(`${API_BASE}/public/slots/candidates`, { cache: 'no-store' }),
        fetch(`${API_BASE}/public/slots/booked`, { cache: 'no-store' }),
      ])
      const cData = await cRes.json()
      const bData = await bRes.json()
      if (cData.status === 'ok') setCandidates(dedupeCandidates(cData.candidates || []))
      if (bData.status === 'ok') setBooked(bData.slots || [])
    } catch { setError('Could not load — check your connection.') }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { refresh() }, [refresh])
  useEffect(() => () => {
    if (slotPreview) URL.revokeObjectURL(slotPreview)
    if (sessionPreview) URL.revokeObjectURL(sessionPreview)
  }, [slotPreview, sessionPreview])

  async function parseScreenshot(file) {
    if (!file) { setParsedSlot(null); return }
    setParsing(true); setError(''); setSuccess('')
    try {
      const fd = new FormData(); fd.append('file', file)
      const res = await fetch(`${API_BASE}/public/slots/parse-screenshot`, { method: 'POST', body: fd })
      const data = await res.json()
      if (!res.ok) { setParsedSlot(null); setError('Auto-read failed — enter date & time manually.'); return }
      setParsedSlot(data.slot || null)
      setInterviewRound(data.slot?.interview_round || '')
      setManualDate(''); setManualTime('')
    } catch { setParsedSlot(null); setError('Network error while reading screenshot') }
    finally { setParsing(false) }
  }

  async function onSlotFileChange(file) {
    if (slotPreview) URL.revokeObjectURL(slotPreview)
    setSlotFile(file || null); setParsedSlot(null); setManualDate(''); setManualTime(''); setInterviewRound(''); setSuccess('')
    if (file) { setSlotPreview(URL.createObjectURL(file)); await parseScreenshot(file) }
    else setSlotPreview('')
  }

  async function onSessionFileChange(file) {
    if (sessionPreview) URL.revokeObjectURL(sessionPreview)
    setSessionFile(file || null)
    if (file) setSessionPreview(URL.createObjectURL(file)); else setSessionPreview('')
  }

  async function uploadPaymentProof() {
    if (!effectiveName || !paymentFile) { setError('Enter your name and attach a payment screenshot first.'); return }
    setBusy(true); setError(''); setSuccess('')
    try {
      const fd = new FormData(); fd.append('name', effectiveName); fd.append('file', paymentFile)
      const res = await fetch(`${API_BASE}/public/slots/payment-proof`, { method: 'POST', body: fd })
      const data = await res.json()
      if (!res.ok) { setError(data.message || 'Payment upload failed'); return }
      setPaymentProofId(data.proof_id || ''); setPaymentFile(null)
      setSuccess('Payment proof saved — you can confirm your slot.')
    } catch { setError('Network error — try again') }
    finally { setBusy(false) }
  }

  async function submitBook(ev) {
    ev.preventDefault()
    if (!effectiveName) { setError('Enter your name.'); return }
    if (!slotFile) { setError('Upload your interview invite screenshot.'); return }
    if (!interviewRound) { setError('Select an interview round (L1, L2, HR, etc.) before confirming.'); return }
    if (selected?.needs_payment_proof && !paymentProofId) { setError(`Upload payment proof first (₹${(selected.balance_due || 0).toLocaleString('en-IN')} due).`); return }
    setBusy(true); setError(''); setSuccess('')
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
      if (!res.ok) { setError(data.payment_due ? (data.message || 'Payment required.') : (data.message || 'Could not book slot')); return }
      if (slotPreview) URL.revokeObjectURL(slotPreview)
      setSlotFile(null); setSlotPreview(''); setParsedSlot(null); setManualDate(''); setManualTime(''); setInterviewRound(''); setPaymentProofId('')
      setSuccess(`Slot confirmed for ${data.candidate?.name || effectiveName}.`)
      setShowUploadMode(false)
      await refresh()
    } catch { setError('Network error — try again') }
    finally { setBusy(false) }
  }

  async function submitSessionComplete(ev) {
    ev.preventDefault()
    if (!effectiveName || !sessionFile) { setError('Enter your name and upload the session complete screenshot.'); return }
    setBusy(true); setError(''); setSuccess('')
    try {
      const fd = new FormData(); fd.append('name', effectiveName); fd.append('file', sessionFile)
      const res = await fetch(`${API_BASE}/public/slots/session-complete`, { method: 'POST', body: fd })
      const data = await res.json()
      if (!res.ok) { setError(data.message || 'Upload failed'); return }
      setSuccess('Session marked complete — thank you.')
      if (sessionPreview) URL.revokeObjectURL(sessionPreview)
      setSessionFile(null); setSessionPreview('')
    } catch { setError('Network error — try again') }
    finally { setBusy(false) }
  }

  // Upcoming slots (exclude current user)
  const upcoming = useMemo(
    () => booked.filter(s => candidateNameKey(s.name) !== candidateNameKey(effectiveName)).slice(0, 8),
    [booked, effectiveName],
  )

  return (
    <div className="sbs-screen">
      <div className="sbs-glow" aria-hidden="true" />
      <div className="sbs-card">

        {/* Header */}
        <header className="sbs-header">
          <div className="sbs-header__text">
            <h1 className="sbs-header__title">Book Interview Slot</h1>
            <p className="sbs-header__sub">Pick the right slot, upload invite, and confirm.</p>
          </div>
          <div className="sbs-header__icon" aria-hidden="true">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
              <rect x="3" y="4" width="18" height="18" rx="3"/>
              <path d="M16 2v4M8 2v4M3 10h18" strokeLinecap="round"/>
            </svg>
          </div>
        </header>

        {/* Tabs */}
        <div className="sbs-tabs" role="tablist">
          <button type="button" role="tab" aria-selected={tab === 'book'}
            className={`sbs-tab${tab === 'book' ? ' sbs-tab--active' : ''}`}
            onClick={() => { setTab('book'); setError(''); setSuccess(''); setShowUploadMode(false) }}>
            Book slot
          </button>
          <button type="button" role="tab" aria-selected={tab === 'session'}
            className={`sbs-tab${tab === 'session' ? ' sbs-tab--active' : ''}`}
            onClick={() => { setTab('session'); setError(''); setSuccess('') }}>
            Session complete
          </button>
        </div>

        {loading ? (
          <div className="sbs-loading"><Spinner size={28} /></div>
        ) : tab === 'session' ? (
          <form className="sbs-form" onSubmit={submitSessionComplete}>
            <label className="sbs-field">
              <span className="sbs-label">Your name</span>
              <SlotCandidatePicker candidates={candidates} value={name} onChange={v => setName(v)} disabled={busy || parsing} />
              <span className="sbs-hint">Pick from the list or type a new client name.</span>
            </label>
            <p className="sbs-lead">Upload the &quot;Session complete&quot; screen after your interview ends.</p>
            <SubmitSlotFileDrop label="Session complete screenshot" file={sessionFile} previewUrl={sessionPreview} disabled={busy} onFile={onSessionFileChange} />
            {error ? <p className="sbs-alert sbs-alert--error" role="alert">{error}</p> : null}
            {success ? <p className="sbs-alert sbs-alert--success">{success}</p> : null}
            <button type="submit" className={`sbs-cta${name.trim() && sessionFile ? ' sbs-cta--ready' : ''}`} disabled={busy || !name.trim() || !sessionFile}>
              {busy ? <Spinner size={18} /> : 'Submit session proof'}
            </button>
          </form>
        ) : (
          <div className="sbs-body">

            {/* STEP 1: Choose slot */}
            {!showUploadMode && (
              <section className="sbs-section">
                <div className="sbs-step-head">
                  <span className="sbs-step-num">1</span>
                  <div>
                    <h2 className="sbs-step-title">Choose your preferred slot</h2>
                    <p className="sbs-step-sub">Select from your confirmed upcoming interview slots.</p>
                  </div>
                </div>
                <div className="sbs-slot-list">
                  {upcoming.length === 0 && !loading && (
                    <p className="sbs-empty">No upcoming slots yet.</p>
                  )}
                  {/* Grouped by date */}
                  {groupSlotsByDate(upcoming).map(({ date, items }) => (
                    <div key={date} className="sbs-date-group">
                      <div className="sbs-date-group__header">
                        <span className="sbs-date-group__label">{formatDayHeader(date)}</span>
                        <span className="sbs-date-group__count">{items.length} slot{items.length !== 1 ? 's' : ''}</span>
                      </div>
                      <div className="sbs-date-group__cards">
                        {items.map((slot, i) => (
                          <SlotCard
                            key={`${slot.name}-${slot.date}-${slot.time}-${i}`}
                            slot={slot}
                            index={upcoming.indexOf(slot)}
                            selected={candidateNameKey(slot.name) === candidateNameKey(name) && candidateNameKey(slot.name) !== ''}
                            onClick={() => { setName(slot.name); setShowUploadMode(true); setError(''); setSuccess('') }}
                          />
                        ))}
                      </div>
                    </div>
                  ))}
                  {/* Can't find slot */}
                  <button type="button" className="sbs-slot-card sbs-slot-card--ghost" onClick={() => { setShowUploadMode(true); setError(''); setSuccess('') }}>
                    <div className="sbs-slot-card__icon sbs-slot-card__icon--ghost">
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
                        <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    </div>
                    <div className="sbs-slot-card__body">
                      <div className="sbs-slot-card__name">Can&apos;t find your slot?</div>
                      <div className="sbs-slot-card__date">
                        Upload <span className="sbs-slot-card__link">invite</span> and we&apos;ll help you find it.
                      </div>
                    </div>
                    <svg className="sbs-slot-card__arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 18l6-6-6-6"/></svg>
                  </button>
                </div>

                {/* Booked slots status */}
                {booked.length > 0 && (
                  <div className="sbs-booked-status">
                    <div className="sbs-booked-status__head">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 6L9 17l-5-5"/></svg>
                      <span>{booked.length} booking{booked.length !== 1 ? 's' : ''} confirmed</span>
                    </div>
                    <div className="sbs-booked-status__list">
                      {booked.slice(0, 5).map((s, i) => (
                        <button
                          key={i}
                          type="button"
                          className="sbs-booked-status__item sbs-booked-status__item--btn"
                          onClick={() => { setName(s.name); setShowUploadMode(true); setError(''); setSuccess('') }}
                        >
                          <div className="sbs-booked-status__item-left">
                            <span className="sbs-booked-status__name">{s.name}</span>
                            <span className="sbs-booked-status__time">{formatFriendlyDate(s.date?.slice(0,10))} · {formatFriendlyTime(s.time)}</span>
                          </div>
                          <div className="sbs-booked-status__item-right">
                            {s.interview_round && <span className="sbs-booked-status__round">{s.interview_round}</span>}
                            <span className="sbs-booked-status__book-btn">Book</span>
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </section>
            )}

            {/* STEP 2: Confirm booking */}
            {showUploadMode && (
              <section className="sbs-section">
                <div className="sbs-step-head">
                  <button type="button" className="sbs-back-btn" onClick={() => { setShowUploadMode(false); setError(''); setSuccess('') }} aria-label="Back">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M15 18l-6-6 6-6"/></svg>
                  </button>
                  <span className="sbs-step-num">2</span>
                  <div>
                    <h2 className="sbs-step-title">Confirm your booking</h2>
                  </div>
                </div>

                <form className="sbs-form" onSubmit={submitBook}>
                  <label className="sbs-field">
                    <span className="sbs-label">Your name</span>
                    <SlotCandidatePicker candidates={candidates} value={name} onChange={v => { setName(v); setPaymentProofId('') }} disabled={busy || parsing} />
                    <span className="sbs-hint">Pick from the list or type a new client name.</span>
                  </label>

                  {selected?.needs_payment_proof && (
                    <div className="sbs-pay-card">
                      <div className="sbs-pay-head"><span>Payment due</span><strong>₹{(selected.balance_due || 0).toLocaleString('en-IN')}</strong></div>
                      {paymentProofId ? <p className="sbs-pay-ok">Payment proof on file ✓</p> : (
                        <>
                          <SubmitSlotFileDrop compact label="Payment screenshot" file={paymentFile} disabled={busy || parsing} busy={busy} onFile={setPaymentFile} />
                          <button type="button" className="sbs-secondary-btn" disabled={busy || parsing || !paymentFile} onClick={uploadPaymentProof}>Save payment proof</button>
                        </>
                      )}
                    </div>
                  )}

                  <label className="sbs-field">
                    <span className="sbs-label">Interview invite screenshot</span>
                    <SubmitSlotFileDrop hint="Teams, Gmail, Calendar, or Zoom — date and time must be visible." file={slotFile} previewUrl={slotPreview} disabled={busy} busy={parsing} onFile={onSlotFileChange} />
                  </label>

                  <label className="sbs-field">
                    <span className="sbs-label">Interview round <span className="sbs-required" aria-hidden="true">*</span></span>
                    <div className={`sbs-select-wrap${!interviewRound && slotFile ? ' sbs-select-wrap--required' : ''}`}>
                      <select className="sbs-select" value={interviewRound} onChange={e => setInterviewRound(e.target.value)} disabled={busy || parsing} required>
                        <option value="">Select round (L1, L2…)</option>
                        {ROUND_OPTIONS.map(r => <option key={r} value={r}>{r}</option>)}
                      </select>
                    </div>
                    {!interviewRound && slotFile && <span className="sbs-hint sbs-hint--warn">Required — select a round to confirm.</span>}
                  </label>

                  {parsing && (
                    <div className="sbs-status sbs-status--loading"><Spinner size={18} /><span>Reading your invite…</span></div>
                  )}

                  {parsedSlot?.date && parsedSlot?.time && (
                    <div className="sbs-detected">
                      <span className="sbs-detected__badge">Detected</span>
                      <div className="sbs-detected__main">
                        <span className="sbs-detected__date">{formatFriendlyDate(parsedSlot.date)}</span>
                        <span className="sbs-detected__time">{formatFriendlyTime(parsedSlot.time)}{parsedSlot.time_end ? ` – ${formatFriendlyTime(parsedSlot.time_end)}` : ''}</span>
                      </div>
                      <div className="sbs-detected__chips">
                        {parsedSlot.interview_round && <span className="sbs-chip">{parsedSlot.interview_round}</span>}
                        {parsedSlot.technology && <span className="sbs-chip sbs-chip--muted">{parsedSlot.technology}</span>}
                        {parsedSlot.platform && <span className="sbs-chip sbs-chip--muted">{platformLabel(parsedSlot.platform)}</span>}
                      </div>
                    </div>
                  )}

                  {showManualSlotFields && (
                    <div className="sbs-manual">
                      <p className="sbs-manual__hint">Include the date line in your screenshot or enter manually.</p>
                      <div className="sbs-manual__grid">
                        <label className="sbs-field"><span className="sbs-label">Interview date</span><input className="sbs-input" type="date" value={manualDate} onChange={e => setManualDate(e.target.value)} disabled={busy || parsing} /></label>
                        <label className="sbs-field"><span className="sbs-label">Start time</span><input className="sbs-input" type="time" value={manualTime} onChange={e => setManualTime(e.target.value)} disabled={busy || parsing} /></label>
                      </div>
                    </div>
                  )}

                  {error && <p className="sbs-alert sbs-alert--error" role="alert">{error}</p>}
                  {success && <p className="sbs-alert sbs-alert--success">{success}</p>}

                  <button type="submit" className={`sbs-cta${canConfirm ? ' sbs-cta--ready' : ''}`} disabled={!canConfirm}>
                    {busy ? <Spinner size={18} /> : 'Confirm booking'}
                  </button>
                </form>
              </section>
            )}

            {/* Trust footer badges */}
            <div className="sbs-trust">
              <div className="sbs-trust__item">
                <span className="sbs-trust__icon sbs-trust__icon--green">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
                </span>
                <div><div className="sbs-trust__title">Secure &amp; Private</div><div className="sbs-trust__sub">Your data is safe with us</div></div>
              </div>
              <div className="sbs-trust__item">
                <span className="sbs-trust__icon sbs-trust__icon--purple">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2" strokeLinecap="round"/></svg>
                </span>
                <div><div className="sbs-trust__title">Smart Detection</div><div className="sbs-trust__sub">We read date &amp; time automatically</div></div>
              </div>
              <div className="sbs-trust__item">
                <span className="sbs-trust__icon sbs-trust__icon--blue">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 6L9 17l-5-5"/></svg>
                </span>
                <div><div className="sbs-trust__title">Instant Confirmation</div><div className="sbs-trust__sub">Get confirmation as soon as you book</div></div>
              </div>
            </div>

          </div>
        )}
      </div>
      <p className="sbs-foot">TeleAutomation · secure slot booking</p>
    </div>
  )
}
