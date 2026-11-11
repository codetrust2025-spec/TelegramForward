import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Spinner } from '../Loader.jsx'
import { SubmitSlotFileDrop } from './SubmitSlotFileDrop.jsx'
import AiProcessingStatus from '../components/AiProcessingStatus.jsx'
import { TwelveHourTimePicker } from './TwelveHourTimePicker.jsx'
import { bookingSourceMeta } from '../utils/bookingSource.js'

const API_BASE = typeof window !== 'undefined' && window.location.port === '3000'
  ? ''
  : (typeof window !== 'undefined' ? `${window.location.protocol}//${window.location.host}` : '')

const TECHNOLOGY_OPTIONS = [
  '.NET',
  'Angular',
  'Automation Testing',
  'AWS Admin',
  'AWS Cloud',
  'AWS DevOps',
  'Azure Admin',
  'Azure DevOps',
  'Business Analyst',
  'Cloud',
  'Cloud DevOps',
  'Data Analyst',
  'Data Engineer',
  'Databricks',
  'DevOps',
  'ETL',
  'Full Stack',
  'Java Backend',
  'ML Engineer',
  'MERN stack',
  'Node JS',
  'Oracle Fusion (Func)',
  'Oracle Fusion (Tech Con)',
  'Power BI',
  'Python',
  'React JS',
  'Salesforce',
  'SAP BASIS',
  'SAP HANA',
  'SAP MM',
  'SAP Sales',
  'ServiceNow',
  'Snowflake',
  'SQL',
  'Testing',
]

function formatFriendlyDate(iso) {
  if (!iso) return ''
  try {
    const d = new Date(`${iso}T12:00:00`)
    return d.toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' })
  } catch { return iso }
}

function formatFriendlyTime(hhmm) {
  if (!hhmm) return ''
  // Already in 12h format? (e.g., "02:00 PM")
  if (/\d{1,2}:\d{2}\s*(AM|PM|am|pm)/i.test(hhmm)) return hhmm
  const [h, m] = hhmm.split(':').map(Number)
  if (Number.isNaN(h)) return hhmm
  const d = new Date()
  d.setHours(h, m || 0, 0, 0)
  return d.toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit', hour12: true })
}

/** Convert any time to 12-hour "hh:mm AM/PM" format */
function normalizeTo12h(val) {
  if (!val) return ''
  val = val.trim()
  // Already 12h? e.g., "02:00 PM", "2:30 pm"
  const m12 = val.match(/^(\d{1,2}):(\d{2})\s*(AM|PM|am|pm)$/i)
  if (m12) { return `${m12[1].padStart(2,'0')}:${m12[2]} ${m12[3].toUpperCase()}` }
  // Short 12h: "2 PM"
  const ms = val.match(/^(\d{1,2})\s*(AM|PM|am|pm)$/i)
  if (ms) { return `${ms[1].padStart(2,'0')}:00 ${ms[2].toUpperCase()}` }
  // 24h: "14:00"
  const m24 = val.match(/^(\d{1,2}):(\d{2})$/)
  if (m24) {
    let h = parseInt(m24[1]), min = m24[2]
    if (h === 0) return `12:${min} AM`
    if (h < 12) return `${String(h).padStart(2,'0')}:${min} AM`
    if (h === 12) return `12:${min} PM`
    return `${String(h-12).padStart(2,'0')}:${min} PM`
  }
  return val
}

/** Convert 12h "02:00 PM" to 24h "14:00" for native inputs or submission */
export function to24h(val) {
  if (!val) return ''
  val = val.trim()
  // Already 24h?
  const m24 = val.match(/^(\d{1,2}):(\d{2})$/)
  if (m24) {
    const hour = Number(m24[1])
    const minute = Number(m24[2])
    if (hour >= 0 && hour <= 23 && minute >= 0 && minute <= 59) {
      return `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`
    }
    return val
  }
  const m = val.match(/^(\d{1,2}):(\d{2})\s*(AM|PM|am|pm)$/i)
  if (!m) return val
  let h = parseInt(m[1]), min = m[2], ap = m[3].toUpperCase()
  if (ap === 'AM' && h === 12) h = 0
  else if (ap === 'PM' && h !== 12) h += 12
  return `${String(h).padStart(2,'0')}:${min}`
}

export function appendInviteTraceFields(fd, { extraction, displayDate, displayTime }) {
  if (extraction?.invite_trace_id) fd.append('invite_trace_id', extraction.invite_trace_id)
  fd.append('invite_display_date', displayDate || '')
  fd.append('invite_display_time', displayTime || '')
  fd.append('invite_extracted_start_time', extraction?.start_time || extraction?.time || '')
}

export function manualSlotFieldsForAiRetry({ manualDate, manualTime, userEditedFields }) {
  return {
    date: userEditedFields?.date ? manualDate : '',
    time: userEditedFields?.time ? manualTime : '',
  }
}

function platformLabel(platform) {
  const map = { teams: 'Microsoft Teams', zoom: 'Zoom', gmail: 'Gmail', google_calendar: 'Google Calendar', barraiser: 'BarRaiser' }
  return map[platform] || platform || ''
}

/** Fix dates where AI/OCR returned wrong year (e.g. 2023 instead of 2026) */
function fixPastYear(dateStr) {
  if (!dateStr) return dateStr
  try {
    const d = new Date(dateStr + 'T00:00:00')
    const today = new Date(); today.setHours(0,0,0,0)
    const diffDays = (today - d) / (1000*60*60*24)
    if (diffDays > 7) {
      // Date is more than 7 days in the past — likely wrong year
      const corrected = new Date(today.getFullYear(), d.getMonth(), d.getDate())
      if ((today - corrected) / (1000*60*60*24) <= 7) return corrected.toISOString().slice(0,10)
      if (corrected > today) return corrected.toISOString().slice(0,10)
      // Still in past with current year, try next year
      const next = new Date(today.getFullYear() + 1, d.getMonth(), d.getDate())
      return next.toISOString().slice(0,10)
    }
    return dateStr
  } catch { return dateStr }
}

/** De-duplicate chip values case-insensitively, removing empties */
function uniqueNonEmptyTags(values) {
  const seen = new Set()
  return values.filter(Boolean).map(v => String(v).trim()).filter(v => {
    const key = v.toLowerCase()
    if (!v || seen.has(key)) return false
    seen.add(key)
    return true
  })
}

export function compactInviteDetectionLabel(extraction) {
  const confidence = Number(extraction?.confidence_score || 0)
  const rawNode = String(
    extraction?.inference_node_label || extraction?.inference_node_id || '',
  ).trim()
  const nodeAliases = {
    rtx4060: 'RTX',
    'rtx 4060': 'RTX',
    jagadeesh: 'Jagadeesh',
    our_machine: 'Praveen',
    praveen: 'Praveen',
  }
  const node = nodeAliases[rawNode.toLowerCase()] || rawNode
  const rawModel = String(
    extraction?.primary_model || extraction?.detected_by || '',
  ).trim()
  const model = rawModel
    .replace(/\s*\([^)]*\)\s*/g, '')
    .split(/\s+\+\s+|\s+verified\b/i)
    .pop()
    .split(':')[0]
    .trim()
  const source = node || model || 'AI'
  const parts = node && model ? [node, model] : [source]
  if (confidence > 0) parts.push(`${confidence}%`)
  return parts.join(' · ')
}

/**
 * Read a fetch Response that is expected to be JSON.
 *
 * Nginx answers an upstream timeout with an HTML 504 page and a restarting
 * backend with an HTML 502, so `res.json()` on its own throws a SyntaxError
 * whose raw text ("Unexpected token '<'") used to reach the candidate.
 * Throw a controlled error instead; callers turn it into friendly copy.
 */
export const INVITE_READ_FAILED_MESSAGE =
  'Could not read the invite. Retry or enter date and time manually.'

export async function readJsonResponse(res) {
  const contentType = String(res.headers?.get?.('content-type') || '')
  if (!contentType.toLowerCase().includes('application/json')) {
    throw new Error(`Expected JSON, received "${contentType || 'unknown'}" (HTTP ${res.status})`)
  }
  let body
  try {
    body = await res.json()
  } catch {
    throw new Error(`Malformed JSON response (HTTP ${res.status})`)
  }
  if (body === null || typeof body !== 'object') {
    throw new Error(`Empty or unusable JSON response (HTTP ${res.status})`)
  }
  return body
}

const ROUND_OPTIONS = ['Screening', 'L1', 'L2', 'Final', 'HR']

function candidateNameKey(value) {
  return String(value || '').trim().toLocaleLowerCase().replace(/[^a-z0-9]/g, '')
}

function formatDayHeader(iso) {
  if (!iso) return ''
  try {
    const d = new Date(`${iso}T12:00:00`)
    const today = new Date()
    const tomorrow = new Date(); tomorrow.setDate(today.getDate() + 1)
    const dateStr = d.toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' })
    if (d.toDateString() === today.toDateString()) return `Today · ${dateStr}`
    if (d.toDateString() === tomorrow.toDateString()) return `Tomorrow · ${dateStr}`
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

function SlotCandidatePicker({ candidates, value, onChange, disabled, inputRef }) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef(null)
  const options = useMemo(() => dedupeCandidates(candidates), [candidates])
  const query = value.trim().toLocaleLowerCase()
  const matches = useMemo(() => options.filter(c => c.name.toLocaleLowerCase().includes(query)), [options, query])
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
        <input ref={inputRef} className="sbs-input sbs-name-input" value={value}
          onChange={e => { onChange(e.target.value); setOpen(true) }}
          onFocus={() => setOpen(true)}
          placeholder="Choose or type your name" disabled={disabled}
          autoComplete="name" aria-autocomplete="list" aria-expanded={open} aria-controls="sbs-candidate-options" />
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
              onClick={() => { onChange(c.name); setOpen(false) }}>{c.name}</button>
          )) : <p className="sbs-picker__empty">Type a new name to continue.</p>}
        </div>
      )}
    </div>
  )
}

/** Compact payment verification summary shown after proof upload. */
function PaymentAiResultCard({ ai }) {
  if (!ai) return null
  const verified = Boolean(ai.verified || ai.booking_eligible || ai.company_payment_verified)
  const referrerVerified = ai.verification_state === 'VERIFIED_REFERRER_PAYMENT'
  const status = ai.status || 'unknown'
  const stateClass = verified ? 'success' : status === 'failed' ? 'error' : 'warn'

  return (
    <div className={`sbs-verify-badge sbs-verify-badge--${stateClass}`} role="status">
      <span>{verified ? '✓' : status === 'failed' ? '✕' : '!'}</span>
      <strong>
        {referrerVerified
          ? 'Referrer payment verified'
          : verified
            ? 'Payment verified'
            : status === 'failed'
              ? 'Payment failed'
              : 'Payment needs review'}
      </strong>
    </div>
  )
}

export function SubmitSlotPage() {
  const [tab, setTab] = useState('book')
  const [candidates, setCandidates] = useState([])
  const [roundWiseCandidates, setRoundWiseCandidates] = useState([])
  const [booked, setBooked] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [parsing, setParsing] = useState(false)
  const parseInFlightRef = useRef(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [name, setName] = useState('')
  const [parsedSlot, setParsedSlot] = useState(null)
  const [slotFile, setSlotFile] = useState(null)
  const [slotPreview, setSlotPreview] = useState('')
  const [paymentProofId, setPaymentProofId] = useState('')
  const [paymentFile, setPaymentFile] = useState(null)
  // Set when the booking call comes back payment_due — round-wise names are typed
  // freely and may not be in the candidate list, so `selected` can't reveal the
  // payment card on its own.
  const [paymentDue, setPaymentDue] = useState(null)
  const [sessionFile, setSessionFile] = useState(null)
  const [sessionPreview, setSessionPreview] = useState('')
  const [manualDate, setManualDate] = useState('')
  const [manualTime, setManualTime] = useState('')
  const [interviewRound, setInterviewRound] = useState('')
  const [roundWiseTechnology, setRoundWiseTechnology] = useState('')
  const [roundWisePhone, setRoundWisePhone] = useState('')
  const [serviceType, setServiceType] = useState('profile_service')
  const [showServiceDrop, setShowServiceDrop] = useState(false)
  const [validationError, setValidationError] = useState(null)
  const [aiExtraction, setAiExtraction] = useState(null)
  const [aiBlocked, setAiBlocked] = useState('')
  // How long the invite read took. Owned here rather than inside
  // AiProcessingStatus because the processing card and the success strip are
  // different elements: swapping them unmounts the card, and a timer living in
  // it would vanish at the exact moment the number becomes worth reading. Held
  // until the file is replaced or the booking is confirmed.
  const [aiElapsedMs, setAiElapsedMs] = useState(null)
  const parseStartedAtRef = useRef(null)
  const submittingRef = useRef(false)
  const [userEditedFields, setUserEditedFields] = useState({})
  const [paymentAiResult, setPaymentAiResult] = useState(null)
  const [paymentAnalysing, setPaymentAnalysing] = useState(false)
  const clientNameRef = useRef(null)
  const roundRef = useRef(null)
  const phoneRef = useRef(null)
  const technologyRef = useRef(null)
  const paymentRef = useRef(null)
  const inviteRef = useRef(null)
  const manualDateRef = useRef(null)
  const manualTimeRef = useRef(null)

  const effectiveName = name.trim()
  const selected = useMemo(() => {
    if (!effectiveName) return null
    const key = effectiveName.toLowerCase()
    const pool = serviceType === 'round_wise' ? roundWiseCandidates : candidates
    return dedupeCandidates(pool).find(c => c.name.toLowerCase() === key) || null
  }, [effectiveName, candidates, roundWiseCandidates, serviceType])

  const bookingSlot = useMemo(() => {
    const effectiveDate = manualDate || parsedSlot?.date || ''
    const effectiveTime = manualTime || parsedSlot?.time || ''
    const effectiveEnd = parsedSlot?.time_end || ''
    if (effectiveDate && effectiveTime) return { ...parsedSlot, date: effectiveDate, time: to24h(effectiveTime), time_end: to24h(effectiveEnd), interview_round: interviewRound }
    return null
  }, [parsedSlot, manualDate, manualTime, interviewRound])

  // With the global OCR switch off there is no second reader, so nothing on
  // this page may mention OCR or present an OCR cross-check as the reason a
  // booking needs manual entry.
  const isAiOnlyMode = aiExtraction?.processing_mode === 'ai'
  const aiOnlyManualHint = (() => {
    const reason = String(aiExtraction?.failure_reason || '')
    if (reason && !reason.includes('OCR')) return reason
    return 'The AI could not read the interview date and start time. Enter them exactly as shown in the invite.'
  })()

  const highConfidenceAiResult = Boolean(
    aiExtraction
    && aiExtraction.auto_booking_safe === true
    && (aiExtraction.interview_date || aiExtraction.date)
    && (aiExtraction.start_time || aiExtraction.time)
    && !aiExtraction.verification_conflict
    && aiExtraction.looks_like_interview_invite !== false
    && !aiExtraction.is_payment_screenshot
  )
  const showManualSlotFields = Boolean(
    slotFile
    && !parsing
    && (
      aiExtraction?.manual_fields_required === true
      || (!highConfidenceAiResult && !parsedSlot?.date)
    )
  )
  // Every round-wise booking must have a freshly verified payment receipt,
  // including a first-time name that is not yet present in the roster.
  const showPaymentCard = serviceType === 'round_wise' || Boolean(selected?.needs_payment_proof || paymentDue)
  const needsPaymentProof = Boolean(showPaymentCard && !paymentProofId)
  const roundWisePhoneDigits = roundWisePhone.replace(/\D/g, '')
  const roundWisePhoneValid = serviceType !== 'round_wise'
    || (roundWisePhoneDigits.length >= 10 && roundWisePhoneDigits.length <= 15)

  // A payment_due answer belongs to one name — drop it as soon as that changes.
  useEffect(() => { setPaymentDue(null) }, [effectiveName, serviceType])

  const validationRefs = {
    client_name: clientNameRef,
    interview_round: roundRef,
    phone: phoneRef,
    technology: technologyRef,
    payment: paymentRef,
    invite: inviteRef,
    invite_datetime: manualDateRef,
  }

  function showValidationError(field, message) {
    setValidationError({ field, message })
    window.requestAnimationFrame(() => {
      const target = validationRefs[field]?.current || inviteRef.current
      target?.scrollIntoView?.({ behavior: 'smooth', block: 'center' })
      target?.focus?.({ preventScroll: true })
    })
  }

  function clearValidationError(field) {
    setValidationError(current => current?.field === field ? null : current)
  }

  function inlineError(field) {
    return validationError?.field === field
      ? <span className="sbs-hint sbs-hint--warn" role="alert">{validationError.message}</span>
      : null
  }

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const [cRes, rRes, bRes] = await Promise.all([
        fetch(`${API_BASE}/public/slots/candidates`, { cache: 'no-store' }),
        fetch(`${API_BASE}/public/slots/candidates?channel=round_wise`, { cache: 'no-store' }),
        fetch(`${API_BASE}/public/slots/booked`, { cache: 'no-store' }),
      ])
      const cData = await cRes.json()
      const rData = await rRes.json()
      const bData = await bRes.json()
      if (cData.status === 'ok') setCandidates(dedupeCandidates(cData.candidates || []))
      // Round-wise names are typed, not picked — this roster is only used to
      // look up a pending balance so the payment card can show before submit.
      if (rData.status === 'ok') setRoundWiseCandidates(dedupeCandidates(rData.candidates || []))
      if (bData.status === 'ok') setBooked(bData.slots || [])
    } catch { setError('Could not load — check your connection.') }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { refresh() }, [refresh])
  useEffect(() => () => {
    if (slotPreview) URL.revokeObjectURL(slotPreview)
    if (sessionPreview) URL.revokeObjectURL(sessionPreview)
  }, [slotPreview, sessionPreview])

  // Tick while the read is in flight; the exact final value is pinned in the
  // parse function's finally block.
  useEffect(() => {
    if (!parsing) return undefined
    const timer = window.setInterval(() => {
      if (parseStartedAtRef.current) {
        setAiElapsedMs(Date.now() - parseStartedAtRef.current)
      }
    }, 100)
    return () => window.clearInterval(timer)
  }, [parsing])

  async function parseScreenshot(file, { preserveUserEdits = false } = {}) {
    if (!file) { setParsedSlot(null); setAiExtraction(null); setAiBlocked(''); return }
    // Extraction is slow, so a second click (or a rapid re-upload) could
    // previously start a parallel request and let the loser overwrite the
    // winner's result. Ignore re-entry while one is already in flight.
    if (parseInFlightRef.current) return
    parseInFlightRef.current = true
    const retained = preserveUserEdits
      ? manualSlotFieldsForAiRetry({ manualDate, manualTime, userEditedFields })
      : { date: '', time: '' }
    setManualDate(retained.date)
    setManualTime(retained.time)
    setParsedSlot(null)
    parseStartedAtRef.current = Date.now()
    setAiElapsedMs(0)
    setParsing(true); setError(''); setSuccess(''); setAiExtraction(null); setAiBlocked('')
    try {
      // Try AI extraction first
      const fd = new FormData(); fd.append('file', file)
      const res = await fetch(`${API_BASE}/public/slots/extract-invite-ai`, { method: 'POST', body: fd })
      // A proxy timeout (504) or a restarting backend (502) replies with an
      // HTML error page. Parsing that blindly surfaced the raw
      // "Unexpected token '<'" SyntaxError to candidates, so confirm the
      // response really is JSON before parsing it.
      const data = await readJsonResponse(res)


      if (res.ok && data.status === 'ok' && data.data) {
        const ext = data.data
        setAiExtraction(ext)
        
        // Check if it's a payment screenshot
        if (ext.is_payment_screenshot) {
          setAiBlocked('This looks like a payment screenshot. Please upload the interview invite screenshot here.')
          setParsedSlot(null)
          setParsing(false)
          return
        }
        // Check if it doesn't look like an invite
        if (ext.looks_like_interview_invite === false) {
          setAiBlocked('This image does not look like an interview invite.')
          setParsedSlot(null)
          setParsing(false)
          return
        }

        // An error response still contains a data object with empty fields.
        // Only stop here when AI returned the minimum usable booking fields;
        // otherwise continue to the deterministic OCR endpoint below.
        const aiDate = ext.interview_date || ext.date
        const aiStartTime = ext.start_time || ext.time
        const allowOllamaTestPrefill = ext.ollama_only_test === true
        if (aiDate && aiStartTime && (ext.auto_booking_safe === true || allowOllamaTestPrefill)) {
          // Auto-fill fields (only if user hasn't manually edited them)
          const slot = {}
          if (!userEditedFields.date) slot.date = aiDate
          if (!userEditedFields.time) slot.time = normalizeTo12h(aiStartTime)
          if ((ext.end_time || ext.time_end) && !userEditedFields.time_end) slot.time_end = normalizeTo12h(ext.end_time || ext.time_end)
          if (ext.meeting_platform) slot.platform = ext.meeting_platform
          if (ext.technology) slot.technology = ext.technology
          if (ext.interview_round && !interviewRound && !userEditedFields.round) {
            setInterviewRound(ext.interview_round)
            slot.interview_round = ext.interview_round
          }

          console.log('[Invite extraction]', { raw: ext, mapped: slot })
          setParsedSlot(slot)
          if (!userEditedFields.date) setManualDate(aiDate)
          if (!userEditedFields.time) setManualTime(normalizeTo12h(aiStartTime))
          setParsing(false)
          return
        }

        console.warn(
          '[Invite extraction] automatic booking blocked',
          ext.failure_stage || 'unknown',
          ext.failure_reason || ext.warnings || ext,
        )
        setParsedSlot(null)
        setParsing(false)
        return
      }
    } catch (e) {
      console.warn('AI extraction failed; automatic booking blocked:', e)
      setParsedSlot(null)
      setAiExtraction({
        confidence_score: 0,
        manual_fields_required: true,
        failure_stage: 'request',
        // Never surface the raw transport/parser error to a candidate; the
        // technical detail goes to the console for operators instead.
        failure_reason: INVITE_READ_FAILED_MESSAGE,
      })
      setAiBlocked('')
      setParsing(false)
      return
    } finally {
      setParsing(false)
      parseInFlightRef.current = false
      // Pin the exact duration however the read ended — success, blocked, or
      // thrown — so the figure shown afterwards is the real one rather than
      // wherever the ticker happened to stop.
      if (parseStartedAtRef.current) {
        setAiElapsedMs(Date.now() - parseStartedAtRef.current)
      }
    }

    // No OCR-only fallback: a single source must never populate booking data.
    setParsedSlot(null)
    setAiExtraction({
      confidence_score: 0,
      manual_fields_required: true,
      failure_stage: 'response',
      failure_reason: 'Invite extraction returned no usable result.',
    })
    setAiBlocked('')
    setParsing(false)
    return
    
  }

  async function onSlotFileChange(file) {
    if (slotPreview) URL.revokeObjectURL(slotPreview)
    setSlotFile(file || null); setParsedSlot(null); setManualDate(''); setManualTime(''); setSuccess(''); setAiExtraction(null); setAiBlocked(''); setUserEditedFields({})
    setAiElapsedMs(null); parseStartedAtRef.current = null
    if (file) clearValidationError('invite')
    if (file) { setSlotPreview(URL.createObjectURL(file)); await parseScreenshot(file) }
    else setSlotPreview('')
  }

  async function onSessionFileChange(file) {
    if (sessionPreview) URL.revokeObjectURL(sessionPreview)
    setSessionFile(file || null)
    if (file) setSessionPreview(URL.createObjectURL(file)); else setSessionPreview('')
  }

  // `file` is passed in when auto-uploading on drop — paymentFile state has not
  // settled yet at that point.
  async function uploadPaymentProof(file = null) {
    const proof = file || paymentFile
    if (!effectiveName || !proof) { setError('Enter your name and attach a payment screenshot first.'); return }
    setBusy(true); setError(''); setSuccess(''); setPaymentAiResult(null); setPaymentAnalysing(true)
    try {
      const fd = new FormData()
      fd.append('name', effectiveName)
      fd.append('service_type', serviceType)
      fd.append('phone', roundWisePhone)
      fd.append('candidate_id', selected?.id || '')
      fd.append('technology', roundWiseTechnology)
      fd.append('interview_round', interviewRound)
      fd.append('file', proof)
      const res = await fetch(`${API_BASE}/public/slots/payment-proof`, { method: 'POST', body: fd })
      const data = await res.json()
      if (!res.ok) { setError(data.message || 'Payment upload failed'); return }
      setPaymentProofId(data.proof_id || ''); setPaymentFile(null)
      clearValidationError('payment')
      const verification = data.ai_extraction || {}
      setSuccess(data.message === 'Previous booking cancelled — payment can be reused.' ? data.message : '')
      // Capture AI extraction result that backend already ran during upload
      if (verification.is_payment_screenshot) {
        setPaymentAiResult(verification)
      }
    } catch { setError('Network error — try again') }
    finally { setBusy(false); setPaymentAnalysing(false) }
  }

  const effectiveBookingDate = manualDate || parsedSlot?.date || ''
  const isPastDate = (() => {
    if (!effectiveBookingDate) return false
    const today = new Date(); today.setHours(0,0,0,0)
    const d = new Date(effectiveBookingDate + 'T00:00:00'); d.setHours(0,0,0,0)
    return d < today
  })()

  async function submitBook(ev) {
    ev.preventDefault()
    setError('')
    if (!effectiveName) return showValidationError('client_name', 'Enter the client name to continue.')
    if (!interviewRound) return showValidationError('interview_round', 'Select the interview round to continue.')
    if (!roundWisePhoneValid) return showValidationError('phone', 'Enter a valid phone number (10–15 digits).')
    if (serviceType === 'round_wise' && !roundWiseTechnology) return showValidationError('technology', 'Select the technology to continue.')
    if (showPaymentCard && (!paymentFile && !paymentProofId)) return showValidationError('payment', 'Upload and verify the payment screenshot to continue.')
    if (showPaymentCard && (!paymentProofId || paymentAnalysing)) return showValidationError('payment', 'Upload and verify the payment screenshot to continue.')
    if (!slotFile) return showValidationError('invite', 'Upload the interview invite screenshot to continue.')
    if (parsing || aiBlocked || !bookingSlot?.date || !bookingSlot?.time) {
      return showValidationError('invite_datetime', parsing
        ? 'Wait for interview invite verification to finish.'
        : 'Verify the interview date and time to continue.')
    }
    if (isPastDate) {
      return showValidationError('invite_datetime', 'Interview date is in the past. Select today or a future date.')
    }
    // `busy` only disables the button after a re-render, so a fast double click
    // could reach the boundary twice. The ref closes that window synchronously.
    if (submittingRef.current) return
    submittingRef.current = true
    setValidationError(null)
    setBusy(true); setError(''); setSuccess('')
    try {
      const fd = new FormData()
      fd.append('name', effectiveName)
      fd.append('service_type', serviceType)
      if (bookingSlot?.date) fd.append('date', bookingSlot.date)
      if (bookingSlot?.time) fd.append('time', bookingSlot.time)
      if (bookingSlot?.time_end) fd.append('time_end', bookingSlot.time_end)
      appendInviteTraceFields(fd, {
        extraction: aiExtraction,
        displayDate: manualDate || parsedSlot?.date || '',
        displayTime: manualTime || parsedSlot?.time || '',
      })
      if (bookingSlot?.interview_round) fd.append('interview_round', bookingSlot.interview_round)
      const technology = serviceType === 'round_wise'
        ? roundWiseTechnology
        : (bookingSlot?.technology || '')
      if (technology) fd.append('technology', technology)
      if (serviceType === 'round_wise') fd.append('phone', roundWisePhone.trim())
      fd.append('candidate_id', selected?.id || '')
      if (paymentProofId) fd.append('payment_proof_id', paymentProofId)
      fd.append(
        'idempotency_key',
        [
          effectiveName.trim().toLowerCase(),
          serviceType,
          roundWisePhone.trim(),
          bookingSlot?.date || '',
          bookingSlot?.time || '',
          bookingSlot?.time_end || '',
          bookingSlot?.interview_round || '',
          paymentProofId,
        ].join('|')
      )
      fd.append('file', slotFile)
      const res = await fetch(`${API_BASE}/bookings/confirm`, { method: 'POST', body: fd })
      const data = await res.json()
      if (!res.ok) {
        if (data.payment_due) {
          // Reveal the payment card so the proof can be uploaded right here.
          setPaymentDue({ balance_due: data.balance_due || 0, name: data.name || effectiveName })
          showValidationError(
            'payment',
            data.message || 'Upload and verify the payment screenshot to continue.',
          )
        } else {
          setError(data.message || 'Could not book slot')
        }
        return
      }
      if (slotPreview) URL.revokeObjectURL(slotPreview)
      setSlotFile(null); setSlotPreview(''); setParsedSlot(null); setManualDate(''); setManualTime(''); setInterviewRound(''); setRoundWiseTechnology(''); setRoundWisePhone(''); setServiceType('profile_service'); setPaymentProofId('')
      setPaymentFile(null)
      setPaymentDue(null)
      setAiExtraction(null)
      setAiBlocked('')
      setAiElapsedMs(null)
      parseStartedAtRef.current = null
      setUserEditedFields({})
      setPaymentAiResult(null)
      setPaymentAnalysing(false)
      setShowServiceDrop(false)
      setName('')
      setValidationError(null)
      setSuccess(`Slot confirmed for ${data.candidate?.name || effectiveName}.`)
      // Refresh data first, then switch to confirmed tab after 2 seconds
      await refresh()
      setTimeout(() => { setTab('confirmed'); setSuccess('') }, 2000)
    } catch { setError('Network error — try again') }
    finally { submittingRef.current = false; setBusy(false) }
  }

  return (
    <div className="sbs-screen submit-slot-screen">
      <div className="sbs-glow" aria-hidden="true" />
      <div className="sbs-card">
        <header className="sbs-header">
          <div className="sbs-header__text">
            <h1 className="sbs-header__title">Book Interview Slot</h1>
            <p className="sbs-header__sub">Pick the slot, upload invite, and confirm.</p>
          </div>
          <div className="sbs-header__icon" aria-hidden="true">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
              <rect x="3" y="4" width="18" height="18" rx="3"/>
              <path d="M16 2v4M8 2v4M3 10h18" strokeLinecap="round"/>
            </svg>
          </div>
        </header>

        <div className="sbs-tabs" role="tablist">
          <button type="button" role="tab" aria-selected={tab === 'book'}
            className={`sbs-tab${tab === 'book' ? ' sbs-tab--active' : ''}`}
            onClick={() => { setTab('book'); setError(''); setSuccess('') }}>
            Book slot
          </button>
          <button type="button" role="tab" aria-selected={tab === 'confirmed'}
            className={`sbs-tab${tab === 'confirmed' ? ' sbs-tab--active' : ''}`}
            onClick={() => { setTab('confirmed'); setError(''); setSuccess('') }}>
            Confirmed slots
          </button>
        </div>

        {loading ? (
          <div className="sbs-loading"><Spinner size={28} /></div>
        ) : tab === 'confirmed' ? (
          /* ── Confirmed slots tab ─────────────────────────── */
          <div className="sbs-body">
            <section className="sbs-section">
              <div className="sbs-step-head">
                <div>
                  <h2 className="sbs-step-title">Confirmed upcoming slots</h2>
                  <p className="sbs-step-sub">{booked.length > 0 ? `${booked.length} interview${booked.length !== 1 ? 's' : ''} scheduled` : 'No confirmed slots yet.'}</p>
                </div>
              </div>
              {booked.length === 0 ? (
                <div className="sbs-confirmed-empty">
                  <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.25" opacity="0.3">
                    <rect x="3" y="4" width="18" height="18" rx="3"/><path d="M16 2v4M8 2v4M3 10h18" strokeLinecap="round"/>
                  </svg>
                  <p>No confirmed slots yet. Book your first slot.</p>
                  <button type="button" className="sbs-cta sbs-cta--ready" style={{maxWidth:'200px'}}
                    onClick={() => { setTab('book'); setError(''); setSuccess('') }}>
                    Book a slot
                  </button>
                </div>
              ) : (
                <div className="sbs-slot-list">
                  {groupSlotsByDate(booked).map(({ date, items }) => (
                    <div key={date} className="sbs-date-group">
                      <div className="sbs-date-group__header">
                        <span className="sbs-date-group__label">{formatDayHeader(date)}</span>
                        <span className="sbs-date-group__count">{items.length} slot{items.length !== 1 ? 's' : ''}</span>
                      </div>
                      <div className="sbs-date-group__cards">
                        {items.map((slot, i) => (
                          <div key={i} className="sbs-confirmed-card">
                            <div className="sbs-slot-card__icon sbs-slot-card__icon--active">
                              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
                                <rect x="3" y="4" width="18" height="18" rx="3"/>
                                <path d="M16 2v4M8 2v4M3 10h18" strokeLinecap="round"/>
                              </svg>
                            </div>
                            <div className="sbs-slot-card__body">
                              <div className="sbs-slot-card__name">{slot.name}</div>
                              <div className="sbs-slot-card__time">
                                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2" strokeLinecap="round"/></svg>
                                <span>{formatFriendlyTime(slot.time)}{slot.time_end ? ` – ${formatFriendlyTime(slot.time_end)}` : ''}</span>
                              </div>
                            </div>
                            <div className="sbs-confirmed-card__right">
                              {slot.interview_round && <span className={`sbs-slot-card__round sbs-slot-card__round--${(slot.interview_round || '').toLowerCase().replace(/\s+/g, '')}`}>{slot.interview_round}</span>}
                              <span className="sbs-confirmed-card__status">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M20 6L9 17l-5-5"/></svg>
                                Booked
                              </span>
                              {(() => {
                                const meta = bookingSourceMeta(slot.interview_booking_source)
                                return (
                                  <span
                                    className={`sbs-source-badge sbs-source-badge--${meta.tone}`}
                                    title={meta.title}
                                  >
                                    {meta.label}
                                  </span>
                                )
                              })()}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>
        ) : (
          /* ── Book slot tab — direct booking form only ─────── */
          <div className="sbs-body">
            <form className="sbs-form" onSubmit={submitBook} noValidate>
              <div className="sbs-field">
                <span className="sbs-label">Service type</span>
                <div className="sbs-select-wrap sbs-select-wrap--custom">
                  <button type="button" className="sbs-select sbs-select--custom" onClick={() => setShowServiceDrop(v => !v)} disabled={busy || parsing}>
                    <span>{serviceType === "round_wise" ? "Round-wise" : "Profile service"}</span>
                    <svg className="sbs-select__arrow" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M6 9l6 6 6-6"/></svg>
                  </button>
                  {showServiceDrop && (
                    <ul className="sbs-dropdown">
                      <li className={`sbs-dropdown__item${serviceType === "round_wise" ? " sbs-dropdown__item--active" : ""}`} onMouseDown={e => e.preventDefault()} onClick={e => { e.stopPropagation(); setServiceType("round_wise"); setShowServiceDrop(false); setName(""); setPaymentProofId(""); setRoundWiseTechnology(""); setRoundWisePhone(""); }}>Round-wise</li>
                      <li className={`sbs-dropdown__item${serviceType === "profile_service" ? " sbs-dropdown__item--active" : ""}`} onMouseDown={e => e.preventDefault()} onClick={e => { e.stopPropagation(); setServiceType("profile_service"); setShowServiceDrop(false); setName(""); setPaymentProofId(""); setRoundWiseTechnology(""); setRoundWisePhone(""); }}>Profile service</li>
                    </ul>
                  )}
                </div>
              </div>

              <label className="sbs-field">
                <span className="sbs-label">Client name</span>
                {serviceType === "round_wise" ? (
                  <input ref={clientNameRef} className="sbs-input" type="text" value={name} onChange={e => { setName(e.target.value); setPaymentProofId(''); if (e.target.value.trim()) clearValidationError('client_name') }} placeholder="Type client name" disabled={busy || parsing} />
                ) : (
                  <SlotCandidatePicker inputRef={clientNameRef} candidates={candidates} value={name} onChange={v => { setName(v); setPaymentProofId(''); if (v.trim()) clearValidationError('client_name') }} disabled={busy || parsing} />
                )}
                {inlineError('client_name')}
                {validationError?.field !== 'client_name' && serviceType === 'round_wise' && (
                  <span className="sbs-hint">Type the client name for this round.</span>
                )}
              </label>

              <label className="sbs-field">
                <span className="sbs-label">Interview round <span className="sbs-required" aria-hidden="true">*</span></span>
                <div className="sbs-select-wrap">
                  <select ref={roundRef} className="sbs-select" value={interviewRound} onChange={e => { setInterviewRound(e.target.value); if (e.target.value) clearValidationError('interview_round') }} disabled={busy || parsing}>
                    <option value="">Select round (L1, L2…)</option>
                    {ROUND_OPTIONS.map(r => <option key={r} value={r}>{r}</option>)}
                  </select>
                </div>
                {inlineError('interview_round')}
              </label>

              {serviceType === 'round_wise' && (
                <>
                  <label className="sbs-field">
                    <span className="sbs-label">Phone number <span className="sbs-required" aria-hidden="true">*</span></span>
                    <input
                      ref={phoneRef}
                      className="sbs-input"
                      type="tel"
                      inputMode="tel"
                      autoComplete="tel"
                      value={roundWisePhone}
                      onChange={e => { setRoundWisePhone(e.target.value); if (e.target.value.replace(/\D/g, '').length >= 10) clearValidationError('phone') }}
                      placeholder="Enter candidate phone number"
                      disabled={busy || parsing}
                    />
                    {inlineError('phone')}
                    {validationError?.field !== 'phone' && (
                      <span className="sbs-hint">Used only for this round-wise candidate record.</span>
                    )}
                  </label>
                  <label className="sbs-field">
                    <span className="sbs-label">Technology <span className="sbs-required" aria-hidden="true">*</span></span>
                    <div className="sbs-select-wrap">
                      <select
                        ref={technologyRef}
                        className="sbs-select"
                        value={roundWiseTechnology}
                        onChange={e => { setRoundWiseTechnology(e.target.value); if (e.target.value) clearValidationError('technology') }}
                        disabled={busy || parsing}
                      >
                        <option value="">Select technology</option>
                        {TECHNOLOGY_OPTIONS.map(technology => (
                          <option key={technology} value={technology}>{technology}</option>
                        ))}
                      </select>
                    </div>
                    {inlineError('technology')}
                  </label>
                </>
              )}
              {showPaymentCard && (
                <div ref={paymentRef} tabIndex={-1} className="sbs-pay-card">
                  <div className="sbs-pay-head"><span>Payment due</span></div>
                  {paymentProofId ? (
                    <>
                      <SubmitSlotFileDrop compact file={paymentFile} disabled={busy || parsing} busy={busy || paymentAnalysing} onFile={f => { setPaymentFile(f); setPaymentProofId(''); setPaymentAiResult(null); if (f) uploadPaymentProof(f) }} />
                      {paymentAiResult && (
                        <PaymentAiResultCard ai={paymentAiResult} />
                      )}
                      {!paymentAiResult && <div className="sbs-verify-badge sbs-verify-badge--success" role="status"><span>✓</span><strong>Payment verified</strong></div>}
                    </>
                  ) : (
                    <>
                      <SubmitSlotFileDrop compact file={paymentFile} disabled={busy || parsing} busy={busy || paymentAnalysing} onFile={f => { setPaymentFile(f); setPaymentAiResult(null); if (f) uploadPaymentProof(f) }} />
                      {paymentAnalysing ? (
                        <div className="sbs-verify-badge sbs-verify-badge--loading">
                          <Spinner size={14} />
                          <strong>Reading payment…</strong>
                        </div>
                      ) : paymentFile && (
                          /* Only reachable when the automatic upload failed. */
                          <button type="button" className="sbs-secondary-btn" disabled={busy || parsing} onClick={() => uploadPaymentProof()}>
                            Retry upload
                          </button>
                        )}
                    </>
                  )}
                  {inlineError('payment')}
                </div>
              )}

              <div ref={inviteRef} tabIndex={-1} className="sbs-field sbs-invite-field">
                <span className="sbs-label">Interview invite screenshot</span>
                <SubmitSlotFileDrop compact file={slotFile} disabled={busy} busy={parsing} onFile={onSlotFileChange} />
                {inlineError('invite')}
                {parsing && (
                  <AiProcessingStatus
                    variant="card"
                    state="processing"
                    title="Reading invite"
                    mode={aiExtraction?.processing_mode || null}
                    elapsedMs={aiElapsedMs}
                  />
                )}
                {!parsing && aiExtraction && !aiBlocked && (
                  <AiProcessingStatus
                    variant="inline"
                    state="success"
                    title="Reading invite"
                    message="AI reading completed"
                    mode={aiExtraction?.processing_mode || null}
                    elapsedMs={aiElapsedMs}
                  />
                )}
                {!parsing && aiBlocked && (
                  <AiProcessingStatus
                    variant="card"
                    state="error"
                    title="Reading invite"
                    message={aiBlocked}
                    mode={aiExtraction?.processing_mode || null}
                    elapsedMs={aiElapsedMs}
                    onRetry={slotFile ? () => parseScreenshot(slotFile, { preserveUserEdits: true }) : undefined}
                    onCancel={() => onSlotFileChange(null)}
                    retryLabel="Retry"
                    cancelLabel="Remove file"
                  />
                )}

              {aiExtraction && !aiBlocked && aiExtraction.confidence_score > 0 && (
                <div className="sbs-detected">
                  <span className={`sbs-detected__badge ${aiExtraction.confidence_score >= 90 ? 'sbs-detected__badge--green' : aiExtraction.confidence_score >= 70 ? 'sbs-detected__badge--yellow' : 'sbs-detected__badge--red'}`}>
                    {compactInviteDetectionLabel(aiExtraction)}
                  </span>
                  <div className="sbs-detected__main">
                    {aiExtraction.interview_date && <span className="sbs-detected__date">{formatFriendlyDate(aiExtraction.interview_date)}</span>}
                    {aiExtraction.start_time && <span className="sbs-detected__time">{aiExtraction.start_time}{aiExtraction.end_time ? ` – ${aiExtraction.end_time}` : ''}</span>}
                  </div>
                  <div className="sbs-detected__chips">
                    {uniqueNonEmptyTags([
                      aiExtraction.meeting_platform ? platformLabel(aiExtraction.meeting_platform) : '',
                      aiExtraction.screenshot_source,
                    ]).map((tag, i) => (
                      <span key={i} className={`sbs-chip${i > 0 ? ' sbs-chip--muted' : ''}`}>{tag}</span>
                    ))}
                  </div>
                </div>
              )}

              {!aiExtraction && parsedSlot?.date && parsedSlot?.time && (
                <div className="sbs-detected">
                  <span className="sbs-detected__badge">Detected</span>
                  <div className="sbs-detected__main">
                    <span className="sbs-detected__date">{formatFriendlyDate(parsedSlot.date)}</span>
                    <span className="sbs-detected__time">{formatFriendlyTime(parsedSlot.time)}{parsedSlot.time_end ? ` – ${formatFriendlyTime(parsedSlot.time_end)}` : ''}</span>
                  </div>
                  <div className="sbs-detected__chips">
                    {parsedSlot.platform && <span className="sbs-chip">{platformLabel(parsedSlot.platform)}</span>}
                  </div>
                </div>
              )}
              </div>

              {showManualSlotFields && (
                <div className="sbs-manual">
                  <p className="sbs-manual__hint">
                    {isAiOnlyMode
                      ? aiOnlyManualHint
                      : aiExtraction?.verification_conflict
                        ? 'Automatic booking was blocked because OCR and AI read different values. Check the invite and enter the correct date and start time.'
                        : aiExtraction?.manual_fields_required
                          ? (aiExtraction.failure_reason || 'Automatic verification could not safely confirm the date and time. Enter the values exactly as shown in the invite.')
                          : parsedSlot?.date
                            ? 'Verify detected date & time — correct below if wrong.'
                            : 'Include the date line in your screenshot or enter manually.'}
                  </p>
                  {!isAiOnlyMode && aiExtraction?.verification_conflict && (
                    <div className="sbs-verification-conflict" role="status">
                      <span>
                        OCR: {aiExtraction.verification_conflict.ocr?.interview_date || 'date not found'}
                        {' · '}
                        {aiExtraction.verification_conflict.ocr?.start_time || 'time not found'}
                      </span>
                      <span>
                        AI: {aiExtraction.verification_conflict.vision?.interview_date || 'date not found'}
                        {' · '}
                        {aiExtraction.verification_conflict.vision?.start_time || 'time not found'}
                      </span>
                    </div>
                  )}
                  <div className="sbs-manual__grid">
                    <label className="sbs-field"><span className="sbs-label">Interview date</span><input ref={manualDateRef} className="sbs-input" type="date" value={manualDate || parsedSlot?.date || ''} onChange={e => { setManualDate(e.target.value); setUserEditedFields(f => ({...f, date: true})); if (e.target.value && (manualTime || parsedSlot?.time)) clearValidationError('invite_datetime') }} disabled={busy || parsing} /></label>
                    <div className="sbs-field">
                      <span className="sbs-label">Start time</span>
                      <TwelveHourTimePicker
                        ref={manualTimeRef}
                        value={manualTime || parsedSlot?.time || ''}
                        onChange={value => { setManualTime(value); setUserEditedFields(f => ({...f, time: true})); if (value && (manualDate || parsedSlot?.date)) clearValidationError('invite_datetime') }}
                        disabled={busy || parsing}
                      />
                      <span className="sbs-hint">Choose the hour, minutes, and AM or PM.</span>
                    </div>
                  </div>
                  {inlineError('invite_datetime')}
                </div>
              )}

              {error && <p className="sbs-alert sbs-alert--error" role="alert">{error}</p>}
              {success && <div className="sbs-alert sbs-alert--success sbs-success-anim"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{flexShrink:0}}><path d="M20 6L9 17l-5-5" strokeLinecap="round" strokeLinejoin="round"/></svg><span>{success}</span></div>}

              <div className="sbs-sticky-action">
                {/* Disabled while the success banner is up: the form has just
                    been cleared, so a ready-looking button there invites a
                    click against an empty form. It re-enables once the banner
                    clears, which keeps the per-field validation guidance that
                    pressing Confirm on an incomplete form is meant to give. */}
                <button type="submit" className="sbs-cta sbs-cta--ready" disabled={busy || parsing || isPastDate || !!aiBlocked || !!success}>
                  <span>{busy ? <Spinner size={18} /> : parsing ? 'Reading invite...' : 'Confirm booking'}</span>
                </button>
              </div>
            </form>
          </div>
        )}
      </div>
    </div>
  )
}
