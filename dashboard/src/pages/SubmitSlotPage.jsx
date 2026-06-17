import React, { useCallback, useEffect, useState } from 'react'
import { Spinner } from '../Loader.jsx'

const API_BASE = typeof window !== 'undefined' && window.location.port === '3000'
  ? ''
  : (typeof window !== 'undefined' ? `${window.location.protocol}//${window.location.host}` : '')

const ROUND_OPTIONS = ['L1', 'L2', 'L3', 'L4', 'HR', 'Final']

function todayIso() {
  const d = new Date()
  const pad = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

export function SubmitSlotPage() {
  const [tab, setTab] = useState('book')
  const [candidates, setCandidates] = useState([])
  const [booked, setBooked] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const [name, setName] = useState('')
  const [date, setDate] = useState(todayIso())
  const [time, setTime] = useState('')
  const [timeEnd, setTimeEnd] = useState('')
  const [interviewRound, setInterviewRound] = useState('L1')
  const [technology, setTechnology] = useState('')
  const [notes, setNotes] = useState('')
  const [slotFile, setSlotFile] = useState(null)
  const [paymentProofId, setPaymentProofId] = useState('')
  const [paymentFile, setPaymentFile] = useState(null)
  const [sessionFile, setSessionFile] = useState(null)
  const [sessionDate, setSessionDate] = useState('')
  const [sessionTime, setSessionTime] = useState('')

  const selected = candidates.find(c => c.name === name)

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
      setSuccess('Payment screenshot saved — you can book your slot now.')
      setPaymentFile(null)
    } catch {
      setError('Network error — try again')
    } finally {
      setBusy(false)
    }
  }

  async function submitBook(ev) {
    ev.preventDefault()
    if (!name || !date || !time) {
      setError('Name, date, and start time are required.')
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
      fd.append('date', date)
      fd.append('time', time)
      if (timeEnd) fd.append('time_end', timeEnd)
      if (interviewRound) fd.append('interview_round', interviewRound)
      if (technology) fd.append('technology', technology)
      if (notes) fd.append('notes', notes)
      if (paymentProofId) fd.append('payment_proof_id', paymentProofId)
      if (slotFile) fd.append('file', slotFile)
      const res = await fetch(`${API_BASE}/public/slots/book`, { method: 'POST', body: fd })
      const data = await res.json()
      if (!res.ok) {
        if (data.payment_due) {
          setError(data.message || 'Payment required before booking.')
        } else {
          setError(data.message || 'Could not book slot')
        }
        return
      }
      setSuccess('Interview slot booked successfully.')
      setSlotFile(null)
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
      setError('Select your name and upload the Session complete screenshot.')
      return
    }
    setBusy(true)
    setError('')
    setSuccess('')
    try {
      const fd = new FormData()
      fd.append('name', name)
      if (sessionDate) fd.append('date', sessionDate)
      if (sessionTime) fd.append('time', sessionTime)
      fd.append('file', sessionFile)
      const res = await fetch(`${API_BASE}/public/slots/session-complete`, { method: 'POST', body: fd })
      const data = await res.json()
      if (!res.ok) {
        setError(data.message || 'Upload failed')
        return
      }
      setSuccess('Session marked complete — thank you.')
      setSessionFile(null)
    } catch {
      setError('Network error — try again')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-screen submit-slot-screen">
      <div className="auth-card submit-slot-card">
        <div className="auth-brand">
          <h1>Interview slots</h1>
          <p>Book a slot or upload session proof — no login required.</p>
        </div>

        <div className="submit-slot-tabs" role="tablist">
          <button
            type="button"
            role="tab"
            className={tab === 'book' ? 'submit-slot-tab submit-slot-tab--active' : 'submit-slot-tab'}
            onClick={() => { setTab('book'); setError(''); setSuccess('') }}
          >
            Book slot
          </button>
          <button
            type="button"
            role="tab"
            className={tab === 'session' ? 'submit-slot-tab submit-slot-tab--active' : 'submit-slot-tab'}
            onClick={() => { setTab('session'); setError(''); setSuccess('') }}
          >
            Session complete
          </button>
        </div>

        {loading ? (
          <div className="submit-slot-loading"><Spinner size={28} /></div>
        ) : (
          <>
            <label className="auth-field">
              <span className="auth-label">Your name</span>
              <select
                className="input auth-input"
                value={name}
                onChange={ev => { setName(ev.target.value); setPaymentProofId('') }}
                disabled={busy}
              >
                <option value="">Select…</option>
                {candidates.map(c => (
                  <option key={c.name} value={c.name}>
                    {c.name}
                    {c.balance_due > 0 ? ` — ₹${c.balance_due.toLocaleString('en-IN')} due` : ''}
                  </option>
                ))}
              </select>
            </label>

            {tab === 'book' ? (
              <form className="submit-slot-form" onSubmit={submitBook}>
                {selected?.needs_payment_proof ? (
                  <div className="submit-slot-pay-block">
                    <p className="submit-slot-hint">
                      Payment due: <strong>₹{(selected.balance_due || 0).toLocaleString('en-IN')}</strong>
                      {paymentProofId ? ' — proof on file ✓' : ' — upload screenshot first'}
                    </p>
                    <label className="auth-field">
                      <span className="auth-label">Payment screenshot</span>
                      <input
                        type="file"
                        accept="image/*"
                        disabled={busy}
                        onChange={ev => setPaymentFile(ev.target.files?.[0] || null)}
                      />
                    </label>
                    <button
                      type="button"
                      className="btn btn--ghost btn--sm"
                      disabled={busy || !paymentFile}
                      onClick={uploadPaymentProof}
                    >
                      Upload payment proof
                    </button>
                  </div>
                ) : null}

                <label className="auth-field">
                  <span className="auth-label">Interview date</span>
                  <input className="input auth-input" type="date" value={date} onChange={ev => setDate(ev.target.value)} required disabled={busy} />
                </label>
                <div className="submit-slot-row">
                  <label className="auth-field">
                    <span className="auth-label">Start time</span>
                    <input className="input auth-input" type="time" value={time} onChange={ev => setTime(ev.target.value)} required disabled={busy} />
                  </label>
                  <label className="auth-field">
                    <span className="auth-label">End time</span>
                    <input className="input auth-input" type="time" value={timeEnd} onChange={ev => setTimeEnd(ev.target.value)} disabled={busy} />
                  </label>
                </div>
                <label className="auth-field">
                  <span className="auth-label">Round</span>
                  <select className="input auth-input" value={interviewRound} onChange={ev => setInterviewRound(ev.target.value)} disabled={busy}>
                    {ROUND_OPTIONS.map(r => <option key={r} value={r}>{r}</option>)}
                  </select>
                </label>
                <label className="auth-field">
                  <span className="auth-label">Technology (optional)</span>
                  <input className="input auth-input" value={technology} onChange={ev => setTechnology(ev.target.value)} placeholder="e.g. React JS" disabled={busy} />
                </label>
                <label className="auth-field">
                  <span className="auth-label">Invite screenshot (optional)</span>
                  <input type="file" accept="image/*" disabled={busy} onChange={ev => setSlotFile(ev.target.files?.[0] || null)} />
                </label>
                <label className="auth-field">
                  <span className="auth-label">Notes (optional)</span>
                  <input className="input auth-input" value={notes} onChange={ev => setNotes(ev.target.value)} disabled={busy} />
                </label>
                {error ? <p className="auth-error" role="alert">{error}</p> : null}
                {success ? <p className="auth-success">{success}</p> : null}
                <button type="submit" className="btn btn--primary auth-submit" disabled={busy || !name}>
                  {busy ? <Spinner size={18} /> : 'Confirm slot'}
                </button>
              </form>
            ) : (
              <form className="submit-slot-form" onSubmit={submitSessionComplete}>
                <p className="submit-slot-hint">Upload your &quot;Session complete&quot; screenshot after the interview.</p>
                <label className="auth-field">
                  <span className="auth-label">Slot date (if multiple slots)</span>
                  <input className="input auth-input" type="date" value={sessionDate} onChange={ev => setSessionDate(ev.target.value)} disabled={busy} />
                </label>
                <label className="auth-field">
                  <span className="auth-label">Slot time (optional)</span>
                  <input className="input auth-input" type="time" value={sessionTime} onChange={ev => setSessionTime(ev.target.value)} disabled={busy} />
                </label>
                <label className="auth-field">
                  <span className="auth-label">Session complete screenshot</span>
                  <input type="file" accept="image/*" required disabled={busy} onChange={ev => setSessionFile(ev.target.files?.[0] || null)} />
                </label>
                {error ? <p className="auth-error" role="alert">{error}</p> : null}
                {success ? <p className="auth-success">{success}</p> : null}
                <button type="submit" className="btn btn--primary auth-submit" disabled={busy || !name}>
                  {busy ? <Spinner size={18} /> : 'Submit session proof'}
                </button>
              </form>
            )}

            {booked.length > 0 ? (
              <section className="submit-slot-booked">
                <h2 className="submit-slot-booked-title">Upcoming booked slots</h2>
                <ul className="submit-slot-booked-list">
                  {booked.slice(0, 12).map((s, i) => (
                    <li key={`${s.name}-${s.date}-${s.time}-${i}`}>
                      <strong>{s.name}</strong>
                      {' — '}
                      {s.date} {s.time}
                      {s.interview_round ? ` (${s.interview_round})` : ''}
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
          </>
        )}
      </div>
    </div>
  )
}
