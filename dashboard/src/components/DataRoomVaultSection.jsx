import React, { useCallback, useState } from 'react'
import { useConfirm } from '../context/ConfirmContext.jsx'
import { copyToClipboard } from '../utils/copyToClipboard.js'

const API_BASE =
  typeof window !== 'undefined' && window.location.port === '3000'
    ? ''
    : typeof window !== 'undefined'
      ? `${window.location.protocol}//${window.location.host}`
      : ''

const DEFAULT_OFFER_FOLDER =
  'https://drive.google.com/drive/folders/1oHMisQJAudp-4RwAG_oMLsbPStd99g8B'

// ── Shared helpers ────────────────────────────────────────────────────────────

function CopyChip({ label, text, copyKey, activeKey, onCopy }) {
  const copied = activeKey === copyKey
  return (
    <button
      type="button"
      className={`dr-copy-btn${copied ? ' dr-copy-btn--copied' : ''}`}
      title={`Copy ${label}`}
      onClick={() => onCopy(copyKey, text)}
    >
      {copied ? 'Copied' : label}
    </button>
  )
}

function serviceCardTone(row) {
  const label = String(row.label || '').toLowerCase()
  if (label.includes('deprecated') || label.includes('legacy')) return 'deprecated'
  if (label.includes('current') || label.includes('2026')) return 'current'
  return 'default'
}

function slugId(text) {
  return String(text || '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 40) || `item_${Date.now()}`
}

// ── Generic vault item modal ──────────────────────────────────────────────────

function VaultModal({ title, fields, form, onChange, onSave, onClose, error }) {
  return (
    <div className="dr-modal-backdrop" role="presentation" onClick={onClose}>
      <div
        className="dr-modal cand-card"
        role="dialog"
        aria-labelledby="dr-vault-modal-title"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="dr-vault-modal-title" className="cand-title">{title}</h2>
        {error && <p className="dr-error">{error}</p>}
        <div className="dr-form-grid">
          {fields.map((f) => (
            <label key={f.key} className={f.full ? 'dr-form-full' : ''}>
              {f.label}
              {f.type === 'textarea' ? (
                <textarea
                  className="cand-input"
                  rows={f.rows || 3}
                  value={form[f.key] || ''}
                  onChange={(e) => onChange({ ...form, [f.key]: e.target.value })}
                />
              ) : (
                <input
                  className="cand-input"
                  type={f.type || 'text'}
                  placeholder={f.placeholder || ''}
                  value={form[f.key] || ''}
                  readOnly={f.readOnly}
                  onChange={(e) => onChange({ ...form, [f.key]: e.target.value })}
                />
              )}
            </label>
          ))}
        </div>
        <div className="dr-modal-actions">
          <button type="button" className="cand-btn" onClick={onClose}>Cancel</button>
          <button type="button" className="cand-btn cand-btn--primary" onClick={onSave}>Save</button>
        </div>
      </div>
    </div>
  )
}

// ── Vault API helpers ─────────────────────────────────────────────────────────

async function vaultCreate(section, body) {
  const res = await fetch(`${API_BASE}/data-room/credentials/vault/${section}`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return res.json()
}

async function vaultUpdate(section, id, body) {
  const res = await fetch(`${API_BASE}/data-room/credentials/vault/${section}/${id}`, {
    method: 'PATCH',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return res.json()
}

async function vaultDelete(section, id) {
  const res = await fetch(`${API_BASE}/data-room/credentials/vault/${section}/${id}`, {
    method: 'DELETE',
    credentials: 'include',
  })
  return res.json()
}

// ── Service Accounts block ────────────────────────────────────────────────────

const SVC_FIELDS = [
  { key: 'id', label: 'ID (stable slug)', placeholder: 'e.g. gmail_karthik_2026' },
  { key: 'label', label: 'Label / title' },
  { key: 'service', label: 'Service (e.g. Gmail)' },
  { key: 'username', label: 'Username / email' },
  { key: 'password', label: 'Password', type: 'password' },
  { key: 'notes', label: 'Notes', full: true },
]

function ServiceAccountsBlock({ accounts, onReload }) {
  const { confirm } = useConfirm()
  const [activeKey, setActiveKey] = useState(null)
  const [modal, setModal] = useState(null)
  const [modalError, setModalError] = useState('')

  const onCopy = useCallback(async (key, text) => {
    const ok = await copyToClipboard(text)
    setActiveKey(ok ? key : null)
    if (ok) window.setTimeout(() => setActiveKey(k => (k === key ? null : k)), 1600)
  }, [])

  const openAdd = () => {
    setModalError('')
    setModal({ mode: 'create', form: { id: '', label: '', service: '', username: '', password: '', notes: '' } })
  }

  const openEdit = (row) => {
    setModalError('')
    setModal({ mode: 'edit', id: row.id, form: { id: row.id, label: row.label || '', service: row.service || '', username: row.username || '', password: row.password || '', notes: row.notes || '' } })
  }

  const handleDelete = async (row) => {
    const ok = await confirm({ title: 'Delete account?', message: `Remove "${row.label || row.id}"?`, confirmLabel: 'Delete', variant: 'danger' })
    if (!ok) return
    await vaultDelete('service_accounts', row.id)
    onReload()
  }

  const handleSave = async () => {
    const { mode, form, id } = modal
    const body = { ...form }
    if (mode === 'create' && !body.id.trim()) body.id = slugId(body.label || body.username)
    const data = mode === 'create'
      ? await vaultCreate('service_accounts', body)
      : await vaultUpdate('service_accounts', id, body)
    if (data.status !== 'ok') { setModalError(data.message || 'Save failed'); return }
    setModal(null)
    onReload()
  }

  return (
    <div className="dr-vault-block">
      <div className="dr-vault-block-head">
        <h3 className="dr-vault-subtitle">Service accounts</h3>
        <button type="button" className="cand-btn cand-btn--sm cand-btn--primary" onClick={openAdd}>+ Add</button>
      </div>
      {accounts.length === 0 ? (
        <p className="dr-muted">No service accounts yet.</p>
      ) : (
        <div className="dr-svc-grid">
          {accounts.map(row => {
            const tone = serviceCardTone(row)
            const copyAll = [row.label || row.id, row.service ? `Service: ${row.service}` : '', row.username ? `Username: ${row.username}` : '', row.password ? `Password: ${row.password}` : '', row.notes || ''].filter(Boolean).join('\n')
            return (
              <article className={`dr-svc-card dr-svc-card--${tone}`} key={row.id}>
                <div className="dr-svc-card-head">
                  <div>
                    <h4 className="dr-svc-card-title">{row.label || row.id}</h4>
                    {row.service && <div className="dr-svc-service">{row.service}</div>}
                  </div>
                  <div className="dr-vault-item-actions">
                    {tone === 'current' && <span className="dr-svc-badge dr-svc-badge--current">Current</span>}
                    {tone === 'deprecated' && <span className="dr-svc-badge dr-svc-badge--deprecated">Old</span>}
                    <button type="button" className="cand-btn cand-btn--sm" onClick={() => openEdit(row)}>Edit</button>
                    <button type="button" className="cand-btn cand-btn--sm cand-btn--danger" onClick={() => handleDelete(row)}>Delete</button>
                  </div>
                </div>
                {row.username && (
                  <div className="dr-svc-field">
                    <span className="dr-svc-field-label">Username</span>
                    <div className="dr-svc-field-value">
                      <code>{row.username}</code>
                      <CopyChip label="Copy" text={row.username} copyKey={`${row.id}-user`} activeKey={activeKey} onCopy={onCopy} />
                    </div>
                  </div>
                )}
                {row.password && (
                  <div className="dr-svc-field">
                    <span className="dr-svc-field-label">Password</span>
                    <div className="dr-svc-field-value">
                      <code className="dr-creds-pass">{row.password}</code>
                      <CopyChip label="Copy" text={row.password} copyKey={`${row.id}-pass`} activeKey={activeKey} onCopy={onCopy} />
                    </div>
                  </div>
                )}
                {row.notes && <p className="dr-svc-notes">{row.notes}</p>}
                <div className="dr-svc-card-actions">
                  <CopyChip label="Copy all" text={copyAll} copyKey={`${row.id}-all`} activeKey={activeKey} onCopy={onCopy} />
                </div>
              </article>
            )
          })}
        </div>
      )}
      {modal && (
        <VaultModal
          title={modal.mode === 'create' ? 'Add service account' : 'Edit service account'}
          fields={SVC_FIELDS.map(f => modal.mode === 'edit' && f.key === 'id' ? { ...f, readOnly: true } : f)}
          form={modal.form}
          onChange={(f) => setModal(s => ({ ...s, form: f }))}
          onSave={handleSave}
          onClose={() => setModal(null)}
          error={modalError}
        />
      )}
    </div>
  )
}

// ── Prompts block ─────────────────────────────────────────────────────────────

const PROMPT_FIELDS = [
  { key: 'id', label: 'ID (stable slug)', placeholder: 'e.g. intro_message' },
  { key: 'title', label: 'Title' },
  { key: 'source', label: 'Source / context' },
  { key: 'body', label: 'Prompt body', type: 'textarea', rows: 8, full: true },
]

function PromptsBlock({ prompts, onReload }) {
  const { confirm } = useConfirm()
  const [activeKey, setActiveKey] = useState(null)
  const [modal, setModal] = useState(null)
  const [modalError, setModalError] = useState('')

  const onCopy = useCallback(async (key, text) => {
    const ok = await copyToClipboard(text)
    setActiveKey(ok ? key : null)
    if (ok) window.setTimeout(() => setActiveKey(k => (k === key ? null : k)), 1600)
  }, [])

  const openAdd = () => {
    setModalError('')
    setModal({ mode: 'create', form: { id: '', title: '', source: '', body: '' } })
  }

  const openEdit = (row) => {
    setModalError('')
    setModal({ mode: 'edit', id: row.id, form: { id: row.id, title: row.title || '', source: row.source || '', body: row.body || '' } })
  }

  const handleDelete = async (row) => {
    const ok = await confirm({ title: 'Delete prompt?', message: `Remove "${row.title || row.id}"?`, confirmLabel: 'Delete', variant: 'danger' })
    if (!ok) return
    await vaultDelete('prompts', row.id)
    onReload()
  }

  const handleSave = async () => {
    const { mode, form, id } = modal
    const body = { ...form }
    if (mode === 'create' && !body.id.trim()) body.id = slugId(body.title)
    const data = mode === 'create'
      ? await vaultCreate('prompts', body)
      : await vaultUpdate('prompts', id, body)
    if (data.status !== 'ok') { setModalError(data.message || 'Save failed'); return }
    setModal(null)
    onReload()
  }

  return (
    <div className="dr-vault-block">
      <div className="dr-vault-block-head">
        <h3 className="dr-vault-subtitle">Prompts</h3>
        <button type="button" className="cand-btn cand-btn--sm cand-btn--primary" onClick={openAdd}>+ Add</button>
      </div>
      {prompts.length === 0 ? (
        <p className="dr-muted">No prompts yet.</p>
      ) : (
        <div className="dr-prompt-list">
          {prompts.map(row => (
            <details className="dr-prompt-card" key={row.id}>
              <summary>
                <span className="dr-prompt-card-title">{row.title || row.id}</span>
                <span className="dr-prompt-card-meta">{(row.body || '').length} chars</span>
                <span className="dr-vault-summary-actions" onClick={(e) => e.stopPropagation()}>
                  <button type="button" className="cand-btn cand-btn--sm" onClick={() => openEdit(row)}>Edit</button>
                  <button type="button" className="cand-btn cand-btn--sm cand-btn--danger" onClick={() => handleDelete(row)}>Delete</button>
                </span>
              </summary>
              <div className="dr-prompt-body-wrap">
                {row.source && <p className="dr-muted">{row.source}</p>}
                <pre className="dr-prompt-body">{row.body}</pre>
                <CopyChip label="Copy prompt" text={row.body || ''} copyKey={`prompt-${row.id}`} activeKey={activeKey} onCopy={onCopy} />
              </div>
            </details>
          ))}
        </div>
      )}
      {modal && (
        <VaultModal
          title={modal.mode === 'create' ? 'Add prompt' : 'Edit prompt'}
          fields={PROMPT_FIELDS.map(f => modal.mode === 'edit' && f.key === 'id' ? { ...f, readOnly: true } : f)}
          form={modal.form}
          onChange={(f) => setModal(s => ({ ...s, form: f }))}
          onSave={handleSave}
          onClose={() => setModal(null)}
          error={modalError}
        />
      )}
    </div>
  )
}

// ── Key Links (resources) block ───────────────────────────────────────────────

const LINK_FIELDS = [
  { key: 'id', label: 'ID (stable slug)', placeholder: 'e.g. drive_folder' },
  { key: 'title', label: 'Title / label' },
  { key: 'url', label: 'URL', placeholder: 'https://' },
  { key: 'notes', label: 'Notes', full: true },
]

function ResourcesBlock({ resources, onReload }) {
  const { confirm } = useConfirm()
  const [modal, setModal] = useState(null)
  const [modalError, setModalError] = useState('')

  const openAdd = () => {
    setModalError('')
    setModal({ mode: 'create', form: { id: '', title: '', url: '', notes: '' } })
  }

  const openEdit = (row) => {
    setModalError('')
    setModal({ mode: 'edit', id: row.id, form: { id: row.id, title: row.title || '', url: row.url || '', notes: row.notes || '' } })
  }

  const handleDelete = async (row) => {
    const ok = await confirm({ title: 'Delete link?', message: `Remove "${row.title || row.url}"?`, confirmLabel: 'Delete', variant: 'danger' })
    if (!ok) return
    await vaultDelete('resources', row.id)
    onReload()
  }

  const handleSave = async () => {
    const { mode, form, id } = modal
    const body = { ...form }
    if (mode === 'create' && !body.id.trim()) body.id = slugId(body.title || body.url)
    const data = mode === 'create'
      ? await vaultCreate('resources', body)
      : await vaultUpdate('resources', id, body)
    if (data.status !== 'ok') { setModalError(data.message || 'Save failed'); return }
    setModal(null)
    onReload()
  }

  return (
    <div className="dr-vault-block">
      <div className="dr-vault-block-head">
        <h3 className="dr-vault-subtitle">Key links</h3>
        <button type="button" className="cand-btn cand-btn--sm cand-btn--primary" onClick={openAdd}>+ Add</button>
      </div>
      {resources.length === 0 ? (
        <p className="dr-muted">No links yet.</p>
      ) : (
        <ul className="dr-resource-grid">
          {resources.map(row => (
            <li className="dr-resource-card" key={row.id}>
              <div className="dr-vault-item-actions dr-vault-item-actions--right">
                <button type="button" className="cand-btn cand-btn--sm" onClick={() => openEdit(row)}>Edit</button>
                <button type="button" className="cand-btn cand-btn--sm cand-btn--danger" onClick={() => handleDelete(row)}>Delete</button>
              </div>
              <a className="dr-resource-card-title" href={row.url} target="_blank" rel="noopener noreferrer" title={row.title || row.url}>
                {row.title || row.url}
              </a>
              {row.notes && <p className="dr-resource-notes">{row.notes}</p>}
            </li>
          ))}
        </ul>
      )}
      {modal && (
        <VaultModal
          title={modal.mode === 'create' ? 'Add link' : 'Edit link'}
          fields={LINK_FIELDS.map(f => modal.mode === 'edit' && f.key === 'id' ? { ...f, readOnly: true } : f)}
          form={modal.form}
          onChange={(f) => setModal(s => ({ ...s, form: f }))}
          onSave={handleSave}
          onClose={() => setModal(null)}
          error={modalError}
        />
      )}
    </div>
  )
}

// ── Offer Letters block ───────────────────────────────────────────────────────

const OFFER_FIELDS = [
  { key: 'id', label: 'ID (stable slug)', placeholder: 'e.g. luxoft_2024_01' },
  { key: 'filename', label: 'Filename' },
  { key: 'candidate', label: 'Candidate name' },
  { key: 'company_name', label: 'Company name' },
  { key: 'date_modified', label: 'Date modified', placeholder: 'YYYY-MM-DD' },
  { key: 'size_kb', label: 'Size (KB)' },
  { key: 'drive_file_id', label: 'Google Drive file ID' },
  { key: 'notes', label: 'Notes', full: true },
]

function OfferLettersBlock({ offers, onReload }) {
  const { confirm } = useConfirm()
  const [modal, setModal] = useState(null)
  const [modalError, setModalError] = useState('')
  const [uploadId, setUploadId] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState('')

  const offerFolder = offers.find(row => row.folder_url)?.folder_url || DEFAULT_OFFER_FOLDER

  const openAdd = () => {
    setModalError('')
    setModal({ mode: 'create', form: { id: '', filename: '', candidate: '', company_name: '', date_modified: '', size_kb: '', drive_file_id: '', notes: '' } })
  }

  const openEdit = (row) => {
    setModalError('')
    setModal({ mode: 'edit', id: row.id, form: { id: row.id, filename: row.filename || '', candidate: row.candidate || '', company_name: row.company_name || '', date_modified: row.date_modified || '', size_kb: String(row.size_kb || ''), drive_file_id: row.drive_file_id || '', notes: row.notes || '' } })
  }

  const handleDelete = async (row) => {
    const ok = await confirm({ title: 'Delete offer letter?', message: `Remove "${row.filename || row.id}"?`, confirmLabel: 'Delete', variant: 'danger' })
    if (!ok) return
    await vaultDelete('offer_letters', row.id)
    onReload()
  }

  const handleSave = async () => {
    const { mode, form, id } = modal
    const body = { ...form }
    if (body.size_kb) body.size_kb = Number(body.size_kb) || body.size_kb
    if (mode === 'create' && !body.id.trim()) body.id = slugId(body.filename || body.candidate)
    const data = mode === 'create'
      ? await vaultCreate('offer_letters', body)
      : await vaultUpdate('offer_letters', id, body)
    if (data.status !== 'ok') { setModalError(data.message || 'Save failed'); return }
    setModal(null)
    onReload()
  }

  const handleUpload = async (rowId, file) => {
    if (!file) return
    setUploadId(rowId)
    setUploading(true)
    setUploadError('')
    const fd = new FormData()
    fd.append('file', file)
    try {
      const res = await fetch(`${API_BASE}/data-room/offer-letters/${rowId}/upload`, { method: 'POST', credentials: 'include', body: fd })
      const data = await res.json()
      if (data.status !== 'ok') setUploadError(data.message || 'Upload failed')
      else onReload()
    } catch (e) {
      setUploadError(String(e))
    } finally {
      setUploading(false)
      setUploadId(null)
    }
  }

  return (
    <div className="dr-vault-block">
      <div className="dr-vault-block-head">
        <h3 className="dr-vault-subtitle">Offer letters</h3>
        <button type="button" className="cand-btn cand-btn--sm cand-btn--primary" onClick={openAdd}>+ Add</button>
      </div>
      <p className="dr-muted dr-offer-folder">
        Drive folder:{' '}
        <a href={offerFolder} target="_blank" rel="noopener noreferrer">Offer letters for proof</a>
      </p>
      {uploadError && <p className="dr-error">{uploadError}</p>}
      {offers.length === 0 ? (
        <p className="dr-muted">No offer letters catalogued yet.</p>
      ) : (
        <div className="cand-table-wrap">
          <table className="cand-table dr-table dr-offer-table">
            <thead>
              <tr>
                <th>File</th>
                <th>Candidate</th>
                <th>Modified</th>
                <th>Size</th>
                <th>Notes</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {offers.map(row => (
                <tr key={row.id}>
                  <td data-label="File">
                    <strong className="dr-offer-filename">{row.filename || row.id}</strong>
                  </td>
                  <td data-label="Candidate">{row.candidate || '—'}</td>
                  <td data-label="Modified">{row.date_modified || '—'}</td>
                  <td data-label="Size">{row.size_kb ? `${row.size_kb} KB` : '—'}</td>
                  <td data-label="Notes" className="dr-summary" title={row.notes}>{row.notes || '—'}</td>
                  <td data-label="Actions" className="dr-actions">
                    <a href={`${API_BASE}/data-room/offer-letters/${row.id}/preview`} target="_blank" rel="noopener noreferrer" className="cand-btn cand-btn--sm">View</a>
                    <a href={`${API_BASE}/data-room/offer-letters/${row.id}/download`} download className="cand-btn cand-btn--sm">Download</a>
                    <label className={`cand-btn cand-btn--sm${uploading && uploadId === row.id ? ' cand-btn--disabled' : ''}`} title="Upload PDF">
                      {uploading && uploadId === row.id ? 'Uploading…' : 'Upload'}
                      <input type="file" accept="application/pdf" style={{ display: 'none' }} onChange={(e) => handleUpload(row.id, e.target.files[0])} />
                    </label>
                    <button type="button" className="cand-btn cand-btn--sm" onClick={() => openEdit(row)}>Edit</button>
                    <button type="button" className="cand-btn cand-btn--sm cand-btn--danger" onClick={() => handleDelete(row)}>Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {modal && (
        <VaultModal
          title={modal.mode === 'create' ? 'Add offer letter' : 'Edit offer letter'}
          fields={OFFER_FIELDS.map(f => modal.mode === 'edit' && f.key === 'id' ? { ...f, readOnly: true } : f)}
          form={modal.form}
          onChange={(f) => setModal(s => ({ ...s, form: f }))}
          onSave={handleSave}
          onClose={() => setModal(null)}
          error={modalError}
        />
      )}
    </div>
  )
}

// ── Main export ───────────────────────────────────────────────────────────────

export function DataRoomVaultSection({ creds, active = true, onReload }) {
  if (!creds) return null

  const accounts = creds.service_accounts || []
  const prompts = creds.prompts || []
  const resources = creds.resources || []
  const offers = creds.offer_letters || []

  return (
    <section
      className={`dr-section dr-vault-section${active ? ' dr-section--active' : ''}`}
      aria-labelledby="dr-vault-title"
    >
      <div className="dr-section-head">
        <h2 id="dr-vault-title" className="dr-section-title">Operations vault</h2>
        <p className="dr-section-desc">
          Gmail accounts, AI prompts, offer-letter catalog, and key links.
        </p>
      </div>

      <div className="dr-vault-stats">
        <div className="dr-vault-stat">
          <div className="dr-vault-stat-label">Accounts</div>
          <div className="dr-vault-stat-value">{accounts.length}</div>
        </div>
        <div className="dr-vault-stat">
          <div className="dr-vault-stat-label">Prompts</div>
          <div className="dr-vault-stat-value">{prompts.length}</div>
        </div>
        <div className="dr-vault-stat">
          <div className="dr-vault-stat-label">Links</div>
          <div className="dr-vault-stat-value">{resources.length}</div>
        </div>
        <div className="dr-vault-stat">
          <div className="dr-vault-stat-label">Offers</div>
          <div className="dr-vault-stat-value">{offers.length}</div>
        </div>
      </div>

      <ServiceAccountsBlock accounts={accounts} onReload={onReload} />
      <PromptsBlock prompts={prompts} onReload={onReload} />
      <OfferLettersBlock offers={offers} onReload={onReload} />
      <ResourcesBlock resources={resources} onReload={onReload} />
    </section>
  )
}
