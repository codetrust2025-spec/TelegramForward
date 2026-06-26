import React, { useState } from 'react'
import { useConfirm } from '../context/ConfirmContext.jsx'

const API_BASE =
  typeof window !== 'undefined' && window.location.port === '3000'
    ? ''
    : typeof window !== 'undefined'
      ? `${window.location.protocol}//${window.location.host}`
      : ''

function slugId(text) {
  return String(text || '').toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 40) || `item_${Date.now()}`
}

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

function VaultModal({ title, fields, form, onChange, onSave, onClose, error }) {
  return (
    <div className="dr-modal-backdrop" role="presentation" onClick={onClose}>
      <div className="dr-modal cand-card" role="dialog" onClick={(e) => e.stopPropagation()}>
        <h2 className="cand-title">{title}</h2>
        {error && <p className="dr-error">{error}</p>}
        <div className="dr-form-grid">
          {fields.map((f) => (
            <label key={f.key} className={f.full ? 'dr-form-full' : ''}>
              {f.label}
              {f.type === 'textarea' ? (
                <textarea className="cand-input" rows={f.rows || 3} value={form[f.key] || ''} onChange={(e) => onChange({ ...form, [f.key]: e.target.value })} />
              ) : (
                <input className="cand-input" type={f.type || 'text'} placeholder={f.placeholder || ''} value={form[f.key] || ''} readOnly={f.readOnly} onChange={(e) => onChange({ ...form, [f.key]: e.target.value })} />
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

export function DataRoomOffersTab({ offers = [], onReload }) {
  const { confirm } = useConfirm()
  const [modal, setModal] = useState(null)
  const [modalError, setModalError] = useState('')
  const [uploading, setUploading] = useState(false)
  const [uploadId, setUploadId] = useState(null)
  const [uploadError, setUploadError] = useState('')

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
    await fetch(`${API_BASE}/data-room/credentials/vault/offer_letters/${row.id}`, { method: 'DELETE', credentials: 'include' })
    onReload()
  }

  const handleSave = async () => {
    const { mode, form, id } = modal
    const body = { ...form }
    if (body.size_kb) body.size_kb = Number(body.size_kb) || body.size_kb
    if (mode === 'create' && !body.id.trim()) body.id = slugId(body.filename || body.candidate)
    const url = mode === 'create'
      ? `${API_BASE}/data-room/credentials/vault/offer_letters`
      : `${API_BASE}/data-room/credentials/vault/offer_letters/${id}`
    const method = mode === 'create' ? 'POST' : 'PATCH'
    const res = await fetch(url, { method, credentials: 'include', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
    const data = await res.json()
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
    <section className="dr-section dr-section--active dr-offers-tab">
      <div className="dr-tab-header">
        <div>
          <h2 className="dr-section-title">Offer Letters</h2>
          <p className="dr-section-desc">Catalogued offer letters for proof in Data Room vault.</p>
        </div>
        <button type="button" className="cand-btn cand-btn--primary" onClick={openAdd}>+ Add offer</button>
      </div>

      <div className="dr-tab-stats">
        <div className="dr-tab-stat">
          <span className="dr-tab-stat-icon dr-tab-stat-icon--blue">📄</span>
          <div>
            <div className="dr-tab-stat-value">{offers.length}</div>
            <div className="dr-tab-stat-label">Total offers</div>
          </div>
        </div>
      </div>

      {uploadError && <p className="dr-error">{uploadError}</p>}

      <div className="dr-tab-table-wrap">
        <table className="dr-tab-table">
          <thead>
            <tr>
              <th>File</th>
              <th>Candidate</th>
              <th>Company</th>
              <th>Modified</th>
              <th>Size</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {offers.length === 0 && (
              <tr><td colSpan={6} className="dr-empty">No offer letters yet.</td></tr>
            )}
            {offers.map(row => (
              <tr key={row.id}>
                <td><strong className="dr-offer-filename">{row.filename || row.id}</strong></td>
                <td>{row.candidate || '—'}</td>
                <td>{row.company_name || '—'}</td>
                <td>{row.date_modified || '—'}</td>
                <td>{row.size_kb ? `${row.size_kb} KB` : '—'}</td>
                <td>
                  <div className="dr-acct-actions">
                    <a href={`${API_BASE}/data-room/offer-letters/${row.id}/preview`} target="_blank" rel="noopener noreferrer" className="dr-offer-icon-btn" title="View">👁</a>
                    <a href={`${API_BASE}/data-room/offer-letters/${row.id}/download`} download className="dr-offer-icon-btn" title="Download">⬇</a>
                    <button type="button" className="cand-btn cand-btn--sm" onClick={() => openEdit(row)}>Edit</button>
                    <button type="button" className="cand-btn cand-btn--sm cand-btn--danger" onClick={() => handleDelete(row)}>Delete</button>
                    <label className={`cand-btn cand-btn--sm${uploading && uploadId === row.id ? ' cand-btn--disabled' : ''}`} title="Upload PDF">
                      {uploading && uploadId === row.id ? '…' : '↑'}
                      <input type="file" accept="application/pdf" style={{ display: 'none' }} onChange={(e) => handleUpload(row.id, e.target.files[0])} />
                    </label>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

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
    </section>
  )
}
