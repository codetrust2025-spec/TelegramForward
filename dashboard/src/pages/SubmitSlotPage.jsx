import React, { useCallback, useEffect, useState } from 'react'
import { Spinner } from '../Loader.jsx'

const API_BASE = typeof window !== 'undefined' && window.location.port === '3000'
  ? ''
  : (typeof window !== 'undefined' ? `${window.location.protocol}//${window.location.host}` : '')

function formatSlotPreview(slot) {
  if (!slot?.date || !slot?.time) return ''
  const end = slot.time_end ? ` – ${slot.time_end}` : ''
  const round = slot.interview_round ? ` · ${slot.interview_round}` : ''
  const tech = slot.technology ? ` · ${slot.technology}` : ''
  return `${slot.date} · ${slot.time}${end}${round}${tech}`
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
  const [paymentProofId, setPaymentProofId] = useState('')
  const [paymentFile, setPaymentFile] = useState(null)
  const [sessionFile, setSessionFile] = useState(null)

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
      setSuccess('Slot details read from your screenshot.')
    } catch {
      setParsedSlot(null)
      setError('Network error while reading screenshot')
    } finally {
      setParsing(false)
    }
  }

  async function onSlotFileChange(file) {
    setSlotFile(file || null)
    setParsedSlot(null)
    setSuccess('')
    if (file) await parseScreenshot(file)
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
    if (!name) {
      setError('Select your name.')
      return
    }
    if (!slotFile) {
      setError('Upload your interview invite screenshot.')
      return
    }
    if (!parsedSlot?.date || !parsedSlot?.time) {
      setError('Waiting for screenshot details — re-upload a clearer invite image.')
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
        if (data.payment_due) {
          setError(data.message || 'Payment required before booking.')
        } else {
          setError(data.message || 'Could not book slot')
        }
        return
      }
      setSuccess('Interview slot booked successfully.')
      setSlotFile(null)
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
      setError('Select your name and upload the Session complete screenshot.')
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
          <p>Upload your invite screenshot — date and time are filled automatically.</p>
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
                disabled={busy || parsing}
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
                        disabled={busy || parsing}
                        onChange={ev => setPaymentFile(ev.target.files?.[0] || null)}
                      />
                    </label>
                    <button
                      type="button"
                      className="btn btn--ghost btn--sm"
                      disabled={busy || parsing || !paymentFile}
                      onClick={uploadPaymentProof}
                    >
                      Upload payment proof
                    </button>
                  </div>
                ) : null}

                <label className="auth-field">
                  <span className="auth-label">Interview invite screenshot *</span>
                  <input
                    type="file"
                    accept="image/*"
                    required
                    disabled={busy || parsing}
                    onChange={ev => onSlotFileChange(ev.target.files?.[0] || null)}
                  />
                </label>

                {parsing ? (
                  <div className="submit-slot-parsed submit-slot-parsed--loading">
                    <Spinner size={20} />
                    <span>Reading date and time from screenshot…</span>
                  </div>
                ) : null}

                {parsedSlot?.date && parsedSlot?.time ? (
                  <div className="submit-slot-parsed">
                    <span className="submit-slot-parsed-label">Detected slot</span>
                    <strong>{formatSlotPreview(parsedSlot)}</strong>
                    {parsedSlot.platform ? (
                      <span className="submit-slot-parsed-sub">{parsedSlot.platform}</span>
                    ) : null}
                  </div>
                ) : null}

                {error ? <p className="auth-error" role="alert">{error}</p> : null}
                {success ? <p className="auth-success">{success}</p> : null}
                <button
                  type="submit"
                  className="btn btn--primary auth-submit"
                  disabled={busy || parsing || !name || !parsedSlot?.date || !parsedSlot?.time}
                >
                  {busy ? <Spinner size={18} /> : 'Confirm slot'}
                </button>
              </form>
            ) : (
              <form className="submit-slot-form" onSubmit={submitSessionComplete}>
                <p className="submit-slot-hint">Upload your &quot;Session complete&quot; screenshot after the interview.</p>
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
