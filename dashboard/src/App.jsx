import React, { useState, useEffect, useRef } from 'react'
import * as XLSX from 'xlsx'

const API = window.location.hostname === 'localhost'
  ? 'http://localhost:8000'
  : `${window.location.protocol}//${window.location.host}`

const WS = window.location.hostname === 'localhost'
  ? 'ws://localhost:8000/ws'
  : `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws`

const SAVED_PHONES = [
  '+916304215610',
  '+919000000001',
  '+919000000001',
  '+918919515419',
  '+919000000005',
  '+917893898866',
  '+917075074573',
]

function StatCard({ label, value, color, sub }) {
  return (
    <div style={{
      background: '#1a1d27', border: `1px solid ${color}33`,
      borderRadius: 12, padding: '20px 24px', flex: 1, minWidth: 140,
    }}>
      <div style={{ fontSize: 13, color: '#94a3b8', marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 36, fontWeight: 700, color }}>{value}</div>
      {sub && <div style={{ fontSize: 12, color: '#64748b', marginTop: 4 }}>{sub}</div>}
    </div>
  )
}

function ProgressBar({ value, max }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0
  const color = pct >= 70 ? '#22c55e' : pct >= 40 ? '#f59e0b' : '#ef4444'
  return (
    <div style={{ marginTop: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ fontSize: 12, color: '#94a3b8' }}>Progress</span>
        <span style={{ fontSize: 12, color }}>{pct}%</span>
      </div>
      <div style={{ background: '#2d3148', borderRadius: 99, height: 8, overflow: 'hidden' }}>
        <div style={{
          width: `${pct}%`, height: '100%', background: color,
          borderRadius: 99, transition: 'width 0.4s ease',
        }} />
      </div>
    </div>
  )
}

function LogEntry({ entry }) {
  const colors = { success: '#22c55e', error: '#ef4444', warning: '#f59e0b', info: '#94a3b8' }
  return (
    <div style={{
      padding: '4px 0', borderBottom: '1px solid #1e2235',
      fontSize: 13, color: colors[entry.level] || '#94a3b8', fontFamily: 'monospace',
    }}>
      {entry.msg}
    </div>
  )
}

function AccountSlot({ slot, label, info, isActive, isRunning, onSwitch, onLogin, onLogout, acctState }) {
  const [step, setStep] = useState('idle') // idle | phone | otp
  const [phone, setPhone] = useState('')
  const [otp, setOtp] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const inputStyle = {
    width: '100%', padding: '9px 12px', borderRadius: 8,
    border: '1px solid #3a3f5c', background: '#0f1117',
    color: '#e2e8f0', fontSize: 13, outline: 'none', boxSizing: 'border-box',
  }
  const btn = (bg, disabled) => ({
    padding: '8px 14px', borderRadius: 8, border: 'none',
    cursor: disabled ? 'not-allowed' : 'pointer',
    background: disabled ? '#2d3148' : bg,
    color: '#fff', fontWeight: 600, fontSize: 13,
    opacity: disabled ? 0.5 : 1,
  })

  async function sendOtp() {
    setLoading(true); setError('')
    const res = await fetch(`${API}/login/send-otp`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phone, slot }),
    })
    const data = await res.json()
    setLoading(false)
    if (data.success) setStep('otp')
    else setError(data.error || 'Failed to send OTP')
  }

  async function verifyOtp() {
    setLoading(true); setError('')
    const res = await fetch(`${API}/login/verify-otp`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: otp }),
    })
    const data = await res.json()
    setLoading(false)
    if (data.success) { setStep('idle'); onLogin(data) }
    else setError(data.error || 'Invalid OTP')
  }

  async function doLogout() {
    setLoading(true)
    await fetch(`${API}/login/logout`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ slot }),
    })
    setLoading(false); setStep('idle'); setPhone('+91'); setOtp(''); setError('')
    onLogout(slot)
  }

  const borderColor = isActive ? '#3b82f6' : '#2d3148'

  return (
    <div style={{
      background: '#1a1d27', borderRadius: 12, padding: '16px 18px',
      border: `2px solid ${borderColor}`, flex: 1, minWidth: 220,
      position: 'relative',
    }}>
      {/* Active badge */}
      {isActive && (
        <div style={{
          position: 'absolute', top: -10, left: 14,
          background: '#3b82f6', color: '#fff', fontSize: 10,
          fontWeight: 700, padding: '2px 8px', borderRadius: 99,
        }}>ACTIVE</div>
      )}

      <div style={{ fontSize: 13, fontWeight: 700, color: '#e2e8f0', marginBottom: 10 }}>
        👤 {label}
      </div>

      {info ? (
        // Logged in
        <div>
          <div style={{ color: '#22c55e', fontSize: 13, fontWeight: 600 }}>✓ {info.name}</div>
          <div style={{ color: '#64748b', fontSize: 12, marginBottom: 6 }}>+{info.phone}</div>
          {/* Per-account live stats */}
          {acctState && (
            <div style={{
              background: '#0f1117', borderRadius: 8, padding: '8px 10px',
              marginBottom: 10, fontSize: 12,
            }}>
              <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                <span style={{ color: acctState.running ? '#22c55e' : '#64748b' }}>
                  {acctState.running ? '● Running' : '○ Idle'}
                </span>
                {acctState.running && acctState.current_group && (
                  <span style={{ color: '#60a5fa' }}>→ {acctState.current_group}</span>
                )}
              </div>
              {(acctState.success > 0 || acctState.failed > 0) && (
                <div style={{ marginTop: 4, display: 'flex', gap: 12 }}>
                  <span style={{ color: '#22c55e' }}>✓ {acctState.success}</span>
                  <span style={{ color: '#ef4444' }}>✗ {acctState.failed}</span>
                  <span style={{ color: '#94a3b8' }}>{acctState.my_groups?.length || 0} groups</span>
                  {acctState.cycle > 0 && <span style={{ color: '#64748b' }}>Cycle {acctState.cycle}</span>}
                </div>
              )}
            </div>
          )}
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {!isActive && (
              <button onClick={() => onSwitch(slot)} style={btn('#3b82f6', false)}>
                ⇄ Set Active
              </button>
            )}
            <button onClick={doLogout} disabled={loading} style={btn('#ef4444', loading)}>
              {loading ? '...' : 'Logout'}
            </button>
          </div>
        </div>
      ) : step === 'idle' ? (
        // Not logged in
        <div>
          <div style={{ color: '#64748b', fontSize: 12, marginBottom: 8 }}>Not logged in</div>
          <button onClick={() => setStep('phone')} style={btn('#22c55e', false)}>
            + Login
          </button>
        </div>
      ) : step === 'phone' ? (
        <div>
          <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 6 }}>Select phone number</div>
          <select
            style={{
              ...inputStyle,
              cursor: 'pointer',
            }}
            value={phone}
            onChange={e => setPhone(e.target.value)}
          >
            <option value="">-- Select number --</option>
            {SAVED_PHONES.map(p => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
          {error && <div style={{ color: '#ef4444', fontSize: 11, marginTop: 4 }}>{error}</div>}
          <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
            <button onClick={sendOtp} disabled={loading || !phone} style={btn('#3b82f6', loading || !phone)}>
              {loading ? 'Sending...' : 'Send OTP'}
            </button>
            <button onClick={() => { setStep('idle'); setError('') }} style={btn('#64748b', false)}>Cancel</button>
          </div>
        </div>
      ) : (
        <div>
          <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 6 }}>
            OTP sent to <span style={{ color: '#60a5fa' }}>{phone}</span>
          </div>
          <input style={inputStyle} placeholder="Enter OTP" value={otp}
            onChange={e => setOtp(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && verifyOtp()} />
          {error && <div style={{ color: '#ef4444', fontSize: 11, marginTop: 4 }}>{error}</div>}
          <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
            <button onClick={verifyOtp} disabled={loading || !otp} style={btn('#22c55e', loading || !otp)}>
              {loading ? 'Verifying...' : 'Verify'}
            </button>
            <button onClick={() => { setStep('phone'); setError('') }} style={btn('#64748b', false)}>← Back</button>
          </div>
        </div>
      )}
    </div>
  )
}

function AccountPanel({ state, onAccountChange }) {
  const accountInfo = state.account_info || {}
  const activeAccount = state.active_account
  const isRunning = state.running

  async function handleSwitch(slot) {
    await fetch(`${API}/account/switch`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ slot }),
    })
    onAccountChange()
  }

  function handleLogin() { onAccountChange() }
  function handleLogout() { onAccountChange() }

  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ fontSize: 13, fontWeight: 700, color: '#94a3b8', marginBottom: 10, letterSpacing: 1 }}>
        📱 ACCOUNTS
        {isRunning && <span style={{ color: '#f59e0b', fontSize: 11, marginLeft: 8 }}>
          (stop forwarding to switch)
        </span>}
      </div>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        {['account1', 'account2'].map((slot, i) => (
          <AccountSlot
            key={slot}
            slot={slot}
            label={`Account ${i + 1}`}
            info={accountInfo[slot]}
            isActive={activeAccount === slot}
            isRunning={isRunning}
            onSwitch={handleSwitch}
            onLogin={handleLogin}
            onLogout={handleLogout}
            acctState={state.account_states?.[slot]}
          />
        ))}
      </div>
    </div>
  )
}

function MessageEditor({ customMessage, onSaved }) {
  const [text, setText] = useState(customMessage || '')
  const [saved, setSaved] = useState(false)
  const [open, setOpen] = useState(false)

  useEffect(() => { setText(customMessage || '') }, [customMessage])

  async function save() {
    await fetch(`${API}/message`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text }),
    })
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
    onSaved()
    setOpen(false)
  }

  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{
        background: '#1a1d27', borderRadius: 12,
        border: '1px solid #3a3f5c', overflow: 'hidden',
      }}>
        {/* Header row */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '12px 18px', cursor: 'pointer',
        }} onClick={() => setOpen(o => !o)}>
          <div style={{ fontSize: 13, fontWeight: 700, color: '#94a3b8', letterSpacing: 1 }}>
            ✉️ MESSAGE TO SEND
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {!open && (
              <span style={{ fontSize: 12, color: '#64748b', maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {text.split('\n')[0]}
              </span>
            )}
            <span style={{ color: '#64748b', fontSize: 12 }}>{open ? '▲ collapse' : '▼ edit'}</span>
          </div>
        </div>

        {open && (
          <div style={{ padding: '0 18px 16px' }}>
            <textarea
              value={text}
              onChange={e => setText(e.target.value)}
              rows={10}
              style={{
                width: '100%', padding: '10px 12px', borderRadius: 8,
                border: '1px solid #3a3f5c', background: '#0f1117',
                color: '#e2e8f0', fontSize: 13, fontFamily: 'monospace',
                resize: 'vertical', outline: 'none', boxSizing: 'border-box',
              }}
            />
            <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
              <button onClick={save} style={{
                padding: '8px 20px', borderRadius: 8, border: 'none',
                cursor: 'pointer', background: saved ? '#22c55e' : '#3b82f6',
                color: '#fff', fontWeight: 600, fontSize: 13,
              }}>
                {saved ? '✓ Saved' : 'Save Message'}
              </button>
              <button onClick={() => setOpen(false)} style={{
                padding: '8px 16px', borderRadius: 8, border: 'none',
                cursor: 'pointer', background: '#2d3148',
                color: '#94a3b8', fontWeight: 600, fontSize: 13,
              }}>
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function GroupsUpload({ currentTotal, onUpdated }) {
  const [open, setOpen] = useState(false)
  const [pasteText, setPasteText] = useState('')
  const [preview, setPreview] = useState([])
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [dragging, setDragging] = useState(false)
  const fileRef = useRef()

  function extractGroupsFromText(text) {
    // Split by newlines, commas, spaces, tabs — grab anything that looks like a username
    return text
      .split(/[\n,\t\r]+/)
      .map(s => s.trim().replace(/^@/, '').replace(/https?:\/\/t\.me\//i, ''))
      .filter(s => s.length > 2 && /^[a-zA-Z0-9_]+$/.test(s))
  }

  function parseFile(file) {
    setError('')
    setPreview([])
    setStatus('')
    const name = file.name.toLowerCase()

    if (name.endsWith('.xlsx') || name.endsWith('.xls') || name.endsWith('.csv')) {
      const reader = new FileReader()
      reader.onload = (e) => {
        try {
          const wb = XLSX.read(e.target.result, { type: 'array' })
          const ws = wb.Sheets[wb.SheetNames[0]]
          const rows = XLSX.utils.sheet_to_csv(ws)
          const groups = extractGroupsFromText(rows)
          setPreview(groups)
          setStatus(`Found ${groups.length} groups from file`)
        } catch (err) {
          setError('Failed to parse file: ' + err.message)
        }
      }
      reader.readAsArrayBuffer(file)
    } else if (name.endsWith('.txt') || name.endsWith('.csv')) {
      const reader = new FileReader()
      reader.onload = (e) => {
        const groups = extractGroupsFromText(e.target.result)
        setPreview(groups)
        setStatus(`Found ${groups.length} groups from file`)
      }
      reader.readAsText(file)
    } else {
      setError('Unsupported file type. Use .xlsx, .xls, .csv, or .txt')
    }
  }

  function handlePaste() {
    const groups = extractGroupsFromText(pasteText)
    setPreview(groups)
    setStatus(`Found ${groups.length} groups from pasted text`)
    setError('')
  }

  async function applyGroups() {
    if (!preview.length) return
    setStatus('Updating...')
    const res = await fetch(`${API}/groups/update`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ groups: preview }),
    })
    const data = await res.json()
    if (data.success) {
      setStatus(`✓ Updated! ${data.total} total groups (${data.added_new} new added, ${data.already_existed} already existed, ${data.skipped_dead} dead skipped).`)
      onUpdated()
      setTimeout(() => { setOpen(false); setPreview([]); setPasteText(''); setStatus('') }, 1500)
    } else {
      setError(data.error || 'Failed to update')
    }
  }

  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{
        background: '#1a1d27', borderRadius: 12,
        border: '1px solid #3a3f5c', overflow: 'hidden',
      }}>
        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '12px 18px', cursor: 'pointer',
        }} onClick={() => setOpen(o => !o)}>
          <div style={{ fontSize: 13, fontWeight: 700, color: '#94a3b8', letterSpacing: 1 }}>
            📂 GROUPS LIST
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 12, color: '#60a5fa' }}>{currentTotal} groups active</span>
            <span style={{ fontSize: 12, color: '#64748b' }}>{open ? '▲ collapse' : '▼ upload'}</span>
          </div>
        </div>

        {open && (
          <div style={{ padding: '0 18px 18px' }}>

            {/* Drop zone */}
            <div
              onDragOver={e => { e.preventDefault(); setDragging(true) }}
              onDragLeave={() => setDragging(false)}
              onDrop={e => { e.preventDefault(); setDragging(false); parseFile(e.dataTransfer.files[0]) }}
              onClick={() => fileRef.current.click()}
              style={{
                border: `2px dashed ${dragging ? '#3b82f6' : '#3a3f5c'}`,
                borderRadius: 10, padding: '24px 16px', textAlign: 'center',
                cursor: 'pointer', marginBottom: 14,
                background: dragging ? '#1e2a3a' : 'transparent',
                transition: 'all 0.2s',
              }}
            >
              <div style={{ fontSize: 28, marginBottom: 6 }}>📁</div>
              <div style={{ fontSize: 13, color: '#94a3b8' }}>
                Drop file here or <span style={{ color: '#3b82f6' }}>click to browse</span>
              </div>
              <div style={{ fontSize: 11, color: '#64748b', marginTop: 4 }}>
                Supports: .xlsx, .xls, .csv, .txt
              </div>
              <input
                ref={fileRef} type="file"
                accept=".xlsx,.xls,.csv,.txt"
                style={{ display: 'none' }}
                onChange={e => e.target.files[0] && parseFile(e.target.files[0])}
              />
            </div>

            {/* Divider */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
              <div style={{ flex: 1, height: 1, background: '#2d3148' }} />
              <span style={{ fontSize: 11, color: '#64748b' }}>OR PASTE FROM GOOGLE SHEETS / NOTES</span>
              <div style={{ flex: 1, height: 1, background: '#2d3148' }} />
            </div>

            {/* Paste area */}
            <textarea
              placeholder={'Paste group usernames here, one per line or comma separated\n\nExamples:\nitandnon\njobsupport0, sapjobsusa\n@reactjsproxysupport\nhttps://t.me/powerbig'}
              value={pasteText}
              onChange={e => setPasteText(e.target.value)}
              rows={6}
              style={{
                width: '100%', padding: '10px 12px', borderRadius: 8,
                border: '1px solid #3a3f5c', background: '#0f1117',
                color: '#e2e8f0', fontSize: 12, fontFamily: 'monospace',
                resize: 'vertical', outline: 'none', boxSizing: 'border-box',
                marginBottom: 8,
              }}
            />
            <button
              onClick={handlePaste}
              disabled={!pasteText.trim()}
              style={{
                padding: '8px 16px', borderRadius: 8, border: 'none',
                cursor: pasteText.trim() ? 'pointer' : 'not-allowed',
                background: pasteText.trim() ? '#7c3aed' : '#2d3148',
                color: '#fff', fontWeight: 600, fontSize: 13,
                opacity: pasteText.trim() ? 1 : 0.5, marginBottom: 14,
              }}
            >
              Extract Groups
            </button>

            {/* Preview */}
            {preview.length > 0 && (
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 6 }}>
                  Preview — {preview.length} groups found:
                </div>
                <div style={{
                  background: '#0f1117', borderRadius: 8, padding: '10px 12px',
                  maxHeight: 160, overflowY: 'auto', fontFamily: 'monospace',
                  fontSize: 12, color: '#60a5fa',
                }}>
                  {preview.map((g, i) => (
                    <div key={i} style={{ padding: '2px 0' }}>@{g}</div>
                  ))}
                </div>
              </div>
            )}

            {error && <div style={{ color: '#ef4444', fontSize: 12, marginBottom: 8 }}>{error}</div>}
            {status && <div style={{ color: '#22c55e', fontSize: 12, marginBottom: 8 }}>{status}</div>}

            {preview.length > 0 && (
              <div style={{ display: 'flex', gap: 8 }}>
                <button onClick={applyGroups} style={{
                  padding: '9px 20px', borderRadius: 8, border: 'none',
                  cursor: 'pointer', background: '#22c55e',
                  color: '#fff', fontWeight: 600, fontSize: 13,
                }}>
                  ✓ Apply {preview.length} Groups
                </button>
                <button onClick={() => { setPreview([]); setPasteText(''); setStatus(''); setError('') }} style={{
                  padding: '9px 16px', borderRadius: 8, border: 'none',
                  cursor: 'pointer', background: '#2d3148',
                  color: '#94a3b8', fontWeight: 600, fontSize: 13,
                }}>
                  Clear
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default function App() {
  const [state, setState] = useState({
    running: false, total: 40, success: 0, failed: 0,
    current_group: '', success_list: [], failed_list: [],
    logs: [], message_id: null, cycle: 0,
    active_account: null, account_info: {}, custom_message: '',
  })
  const [connected, setConnected] = useState(false)
  const [activeTab, setActiveTab] = useState('logs')
  const [showGroups, setShowGroups] = useState(false)
  const [groups, setGroups] = useState([])
  const [groupSearch, setGroupSearch] = useState('')
  const [copied, setCopied] = useState(false)
  const logsEndRef = useRef(null)  // kept for compatibility but unused
  const wsRef = useRef(null)

  useEffect(() => {
    connect()
    return () => wsRef.current?.close()
  }, [])

  const logsContainerRef = useRef(null)
  const userScrolledUp = useRef(false)

  useEffect(() => {
    const el = logsContainerRef.current
    if (!el) return
    // Only auto-scroll to bottom if user hasn't scrolled up manually
    if (!userScrolledUp.current && activeTab === 'logs') {
      el.scrollTop = el.scrollHeight
    }
  }, [state.logs, activeTab])

  function handleLogsScroll(e) {
    const el = e.target
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40
    userScrolledUp.current = !atBottom
  }

  function connect() {
    const ws = new WebSocket(WS)
    wsRef.current = ws
    ws.onopen = () => setConnected(true)
    ws.onclose = () => { setConnected(false); setTimeout(connect, 3000) }
    ws.onerror = () => ws.close()
    ws.onmessage = (e) => {
      const data = JSON.parse(e.data)
      if (data.type === 'state') setState(data)
    }
  }

  async function refreshAccounts() {
    const res = await fetch(`${API}/account/status`)
    const data = await res.json()
    const msgRes = await fetch(`${API}/message`)
    const msgData = await msgRes.json()
    setState(prev => ({
      ...prev,
      active_account: data.active_account,
      account_info: data.account_info || {},
      custom_message: msgData.message || prev.custom_message,
    }))
  }

  const loggedIn = !!(state.active_account && state.account_info?.[state.active_account])

  async function startForwarding() {
    await fetch(`${API}/start`, { method: 'POST' })
  }
  async function startTest() {
    await fetch(`${API}/start-test`, { method: 'POST' })
  }
  async function stopForwarding() {
    await fetch(`${API}/stop`, { method: 'POST' })
    setState(prev => ({ ...prev, running: false, current_group: '' }))
  }

  async function openGroups() {
    if (groups.length === 0) {
      const res = await fetch(`${API}/groups`)
      const data = await res.json()
      setGroups(data.groups)
    }
    setGroupSearch('')
    setShowGroups(true)
  }

  function downloadGroups() {
    const text = groups.map((g, i) => `${i + 1}. ${g}`).join('\n')
    const blob = new Blob([`Telegram Groups List (${groups.length} total)\n${'='.repeat(40)}\n\n${text}`], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'groups_list.txt'
    a.click()
    URL.revokeObjectURL(url)
  }

  const activeAcctState = state.account_states?.[state.active_account]

  const [countdown, setCountdown] = useState(0)
  const [cycleElapsed, setCycleElapsed] = useState(0)
  const cycleStartRef = useRef(null)

  // Sync countdown from server
  useEffect(() => {
    const serverVal = activeAcctState?.next_cycle_in ?? 0
    if (serverVal > 0) setCountdown(serverVal)
  }, [activeAcctState?.next_cycle_in])

  // Count down every second
  useEffect(() => {
    if (countdown <= 0) return
    const timer = setInterval(() => {
      setCountdown(prev => Math.max(0, prev - 1))
    }, 1000)
    return () => clearInterval(timer)
  }, [countdown > 0])

  // Track cycle elapsed time
  useEffect(() => {
    if (state.running) {
      if (!cycleStartRef.current) cycleStartRef.current = Date.now()
      const timer = setInterval(() => {
        setCycleElapsed(Math.floor((Date.now() - cycleStartRef.current) / 1000))
      }, 1000)
      return () => clearInterval(timer)
    } else {
      cycleStartRef.current = null
      setCycleElapsed(0)
    }
  }, [state.running])
  const displaySuccess = activeAcctState?.success ?? state.success
  const displayFailed = activeAcctState?.failed ?? state.failed
  const displayCurrentGroup = activeAcctState?.current_group || state.current_group
  const displayActiveGroups = activeAcctState?.active_groups ?? state.active_groups
  const displaySuccessList = activeAcctState?.success_list ?? state.success_list
  const displayFailedList = activeAcctState?.failed_list ?? state.failed_list

  const total = displaySuccess + displayFailed
  const successRate = total > 0 ? ((displaySuccess / total) * 100).toFixed(1) : '0.0'
  const processed = displaySuccess + displayFailed
  const progressMax = state.total || 1
  // skipped = groups where our msg was already last (didn't need sending)
  const skipped = progressMax - (displayActiveGroups || 0)
  // Only show progress if a cycle has actually run
  const hasCycleRun = (activeAcctState?.cycle ?? 0) > 0
  const progressValue = hasCycleRun ? Math.min(progressMax, skipped + processed) : 0

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '24px 16px' }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: '#e2e8f0' }}>📡 Telegram Forwarder</h1>
          <div style={{ fontSize: 13, color: '#64748b', marginTop: 2 }}>
            {state.cycle > 0 ? <span>Cycle #{state.cycle} · </span> : ''}
            {state.active_account && state.account_info?.[state.active_account] && (
              <span style={{ color: '#22c55e' }}>
                {state.account_info[state.active_account].name} active
              </span>
            )}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{
            width: 8, height: 8, borderRadius: '50%',
            background: connected ? '#22c55e' : '#ef4444',
            boxShadow: connected ? '0 0 6px #22c55e' : 'none',
          }} />
          <span style={{ fontSize: 12, color: '#64748b' }}>{connected ? 'Connected' : 'Reconnecting...'}</span>
        </div>
      </div>

      {/* Account Panel */}
      <AccountPanel state={state} onAccountChange={refreshAccounts} />

      {/* Message Editor */}
      <MessageEditor customMessage={state.custom_message} onSaved={refreshAccounts} />

      {/* Groups Upload */}
      <GroupsUpload currentTotal={state.total || 0} onUpdated={refreshAccounts} />

      {/* Stat Cards */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap' }}>
        <StatCard label="Total Groups" value={state.total || 0} color="#60a5fa" />
        <StatCard label="Need Re-send" value={displayActiveGroups} color="#a78bfa" sub="our msg not last" />
        <StatCard label="Success" value={displaySuccess} color="#22c55e" />
        <StatCard label="Failed" value={displayFailed} color="#ef4444" />
        <StatCard
          label="Success Rate"
          value={`${successRate}%`}
          color={parseFloat(successRate) >= 70 ? '#22c55e' : parseFloat(successRate) >= 40 ? '#f59e0b' : '#ef4444'}
          sub={`${processed} / ${state.total || 0} sent`}
        />
      </div>

      {/* Progress */}
      <div style={{ background: '#1a1d27', borderRadius: 12, padding: '16px 20px', marginBottom: 20 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <span style={{ fontSize: 14, fontWeight: 600 }}>
            {state.running ? (
              <span>
                <span style={{ color: '#22c55e', marginRight: 6 }}>●</span>
                Forwarding to: <span style={{ color: '#60a5fa' }}>{displayCurrentGroup || '...'}</span>
              </span>
            ) : countdown > 0 ? (
              <span>
                <span style={{ color: '#fbbf24', marginRight: 6 }}>⏳</span>
                Next cycle in: <span style={{ color: '#fbbf24', fontWeight: 700, fontSize: 16, fontFamily: 'monospace' }}>
                  {Math.floor(countdown / 60)}m {String(countdown % 60).padStart(2, '0')}s
                </span>
              </span>
            ) : 'Idle'}
          </span>
          <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
            {state.running && cycleElapsed > 0 && (
              <span style={{ fontSize: 13, color: '#e2e8f0', fontWeight: 600, fontFamily: 'monospace' }}>
                ⏱ <span style={{ color: '#38bdf8' }}>{Math.floor(cycleElapsed / 60)}m {String(cycleElapsed % 60).padStart(2, '0')}s</span> elapsed
              </span>
            )}
            <span style={{ fontSize: 12, color: '#94a3b8' }}>{progressValue} / {progressMax}</span>
          </div>
        </div>
        <ProgressBar value={progressValue} max={progressMax} />
      </div>

      {/* Controls */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 24, flexWrap: 'wrap' }}>
        <button onClick={startTest} disabled={state.running || !loggedIn} style={{
          padding: '10px 20px', borderRadius: 8, border: 'none',
          cursor: (state.running || !loggedIn) ? 'not-allowed' : 'pointer',
          background: (state.running || !loggedIn) ? '#2d3148' : '#3b82f6',
          color: '#fff', fontWeight: 600, fontSize: 14,
          opacity: (state.running || !loggedIn) ? 0.5 : 1,
        }}>
          🧪 Test (One-Shot)
        </button>
        <button onClick={startForwarding} disabled={state.running || !loggedIn} style={{
          padding: '10px 20px', borderRadius: 8, border: 'none',
          cursor: (state.running || !loggedIn) ? 'not-allowed' : 'pointer',
          background: (state.running || !loggedIn) ? '#2d3148' : '#22c55e',
          color: '#fff', fontWeight: 600, fontSize: 14,
          opacity: (state.running || !loggedIn) ? 0.5 : 1,
        }}>
          ▶ Start Auto (rotation)
        </button>
        <button onClick={stopForwarding} disabled={!state.running} style={{
          padding: '10px 20px', borderRadius: 8, border: 'none',
          cursor: !state.running ? 'not-allowed' : 'pointer',
          background: !state.running ? '#2d3148' : '#ef4444',
          color: '#fff', fontWeight: 600, fontSize: 14,
          opacity: !state.running ? 0.5 : 1,
        }}>
          ⏹ Stop
        </button>
        <button onClick={openGroups} style={{
          padding: '10px 20px', borderRadius: 8, border: 'none',
          cursor: 'pointer', background: '#7c3aed',
          color: '#fff', fontWeight: 600, fontSize: 14,
        }}>
          📋 View Groups ({state.total || 40})
        </button>
        <button onClick={() => {
          setState(prev => ({
            ...prev,
            success: 0, failed: 0, logs: [],
            success_list: [], failed_list: [],
            current_group: '', active_groups: 0,
            account_states: {
              account1: { ...prev.account_states?.account1, success: 0, failed: 0, logs: [], success_list: [], failed_list: [], current_group: '' },
              account2: { ...prev.account_states?.account2, success: 0, failed: 0, logs: [], success_list: [], failed_list: [], current_group: '' },
            }
          }))
        }} style={{
          padding: '10px 20px', borderRadius: 8, border: 'none',
          cursor: 'pointer', background: '#475569',
          color: '#fff', fontWeight: 600, fontSize: 14,
        }}>
          🔄 Reset
        </button>
      </div>

      {/* Groups Modal */}
      {showGroups && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          zIndex: 1000, padding: 16,
        }} onClick={() => setShowGroups(false)}>
          <div style={{
            background: '#1a1d27', borderRadius: 16, padding: 24,
            width: '100%', maxWidth: 600, maxHeight: '80vh',
            display: 'flex', flexDirection: 'column',
            border: '1px solid #3a3f5c',
          }} onClick={e => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <h2 style={{ fontSize: 18, fontWeight: 700, color: '#e2e8f0' }}>
                📋 Groups List ({groups.length})
              </h2>
              <div style={{ display: 'flex', gap: 8 }}>
                <button onClick={downloadGroups} style={{
                  padding: '7px 14px', borderRadius: 8, border: 'none',
                  cursor: 'pointer', background: '#22c55e', color: '#fff',
                  fontWeight: 600, fontSize: 13,
                }}>
                  ⬇ Download
                </button>
                <button onClick={() => setShowGroups(false)} style={{
                  padding: '7px 14px', borderRadius: 8, border: 'none',
                  cursor: 'pointer', background: '#3a3f5c', color: '#fff',
                  fontWeight: 600, fontSize: 13,
                }}>
                  ✕ Close
                </button>
              </div>
            </div>
            <input
              placeholder="Search groups..."
              value={groupSearch}
              onChange={e => setGroupSearch(e.target.value)}
              style={{
                padding: '9px 14px', borderRadius: 8, border: '1px solid #3a3f5c',
                background: '#0f1117', color: '#e2e8f0', fontSize: 14,
                marginBottom: 12, outline: 'none',
              }}
            />
            <div style={{ overflowY: 'auto', flex: 1 }}>
              {groups
                .filter(g => g.toLowerCase().includes(groupSearch.toLowerCase()))
                .map((g, i) => (
                  <div key={i} style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '7px 4px', borderBottom: '1px solid #1e2235',
                  }}>
                    <span style={{ fontSize: 13, color: '#94a3b8', minWidth: 36 }}>{i + 1}.</span>
                    <a href={`https://t.me/${g}`} target="_blank" rel="noreferrer"
                      style={{ fontSize: 13, color: '#60a5fa', textDecoration: 'none', flex: 1 }}>
                      {g}
                    </a>
                    <a href={`https://t.me/${g}`} target="_blank" rel="noreferrer"
                      style={{ fontSize: 11, color: '#64748b', textDecoration: 'none' }}>
                      t.me/{g} ↗
                    </a>
                  </div>
                ))}
            </div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 12, alignItems: 'center', width: '100%' }}>
        {['logs', 'success', 'failed'].map(tab => (
          <button key={tab} onClick={() => setActiveTab(tab)} style={{
            padding: '7px 16px', borderRadius: 8, border: 'none',
            cursor: 'pointer', fontSize: 13, fontWeight: 600,
            background: activeTab === tab ? '#3b82f6' : '#1a1d27',
            color: activeTab === tab ? '#fff' : '#94a3b8',
          }}>
            {tab === 'logs' && `📋 Logs (${state.logs.length})`}
            {tab === 'success' && `✅ Success (${displaySuccessList.length})`}
            {tab === 'failed' && `❌ Failed (${displayFailedList.length})`}
          </button>
        ))}
        <div style={{ flex: 1 }} />
        <button
          onClick={() => {
            let text = ''
            if (activeTab === 'logs') {
              text = state.logs.map(e => e.msg).join('\n')
            } else if (activeTab === 'success') {
              text = displaySuccessList.join('\n')
            } else {
              text = displayFailedList.map(e => `${e.group} — ${e.reason}`).join('\n')
            }
            navigator.clipboard.writeText(text).then(() => {
              setCopied(true)
              setTimeout(() => setCopied(false), 2000)
            })
          }}
          disabled={state.logs.length === 0}
          style={{
            padding: '7px 16px', borderRadius: 8, border: 'none',
            cursor: state.logs.length === 0 ? 'not-allowed' : 'pointer', fontSize: 13, fontWeight: 600,
            background: copied ? '#22c55e' : state.logs.length === 0 ? '#1a1d27' : '#2d3148',
            color: state.logs.length === 0 ? '#3a3f5c' : '#fff',
            transition: 'background 0.2s',
            whiteSpace: 'nowrap',
          }}
        >
          {copied ? '✓ Copied!' : '📄 Copy'}
        </button>
      </div>

      {/* Tab Content */}
      <div
        ref={logsContainerRef}
        onScroll={handleLogsScroll}
        style={{
          background: '#1a1d27', borderRadius: 12, padding: '12px 16px',
          height: 380, overflowY: 'auto',
        }}
      >
        {activeTab === 'logs' && (
          <>
            {state.logs.length === 0 && (
              <div style={{ color: '#64748b', fontSize: 13, textAlign: 'center', marginTop: 40 }}>
                No logs yet. Start forwarding to see live updates.
              </div>
            )}
            {state.logs.map((entry, i) => <LogEntry key={i} entry={entry} />)}
          </>
        )}
        {activeTab === 'success' && (
          <>
            {displaySuccessList.length === 0 && (
              <div style={{ color: '#64748b', fontSize: 13, textAlign: 'center', marginTop: 40 }}>
                No successful forwards yet.
              </div>
            )}
            {displaySuccessList.map((group, i) => (
              <div key={i} style={{
                padding: '6px 0', borderBottom: '1px solid #1e2235',
                fontSize: 13, color: '#22c55e', fontFamily: 'monospace',
                display: 'flex', alignItems: 'center', gap: 8,
              }}>
                <span>✓</span>
                <a href={`https://t.me/${group}`} target="_blank" rel="noreferrer"
                  style={{ color: '#22c55e', textDecoration: 'none' }}>{group}</a>
              </div>
            ))}
          </>
        )}
        {activeTab === 'failed' && (
          <>
            {displayFailedList.length === 0 && (
              <div style={{ color: '#64748b', fontSize: 13, textAlign: 'center', marginTop: 40 }}>
                No failures yet.
              </div>
            )}
            {displayFailedList.map((item, i) => (
              <div key={i} style={{ padding: '6px 0', borderBottom: '1px solid #1e2235', fontSize: 13 }}>
                <span style={{ color: '#ef4444', fontFamily: 'monospace' }}>✗ {item.group}</span>
                <div style={{ color: '#64748b', fontSize: 11, marginTop: 2, paddingLeft: 14 }}>
                  {item.reason}
                </div>
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  )
}
