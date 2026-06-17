import React, { useCallback, useEffect, useRef, useState } from 'react'
import { useConfirm } from '../context/ConfirmContext.jsx'
import { copyToClipboard } from '../utils/copyToClipboard.js'
import { offerLetterPreviewEmbed, offerLetterPreviewApiUrl } from '../utils/offerLetterUrls.js'
import {
  createVaultItem,
  deleteVaultItem,
  updateVaultItem,
} from '../utils/dataRoomCredentialsApi.js'
import { PdfPreviewPane } from './PdfPreviewPane.jsx'
import { API } from '../config.js'

const DEFAULT_OFFER_FOLDER =
  'https://drive.google.com/drive/folders/1oHMisQJAudp-4RwAG_oMLsbPStd99g8B'

const VAULT_TABS = [
  { id: 'service_accounts', label: 'Accounts' },
  { id: 'prompts', label: 'Prompts' },
  { id: 'resources', label: 'Links' },
  { id: 'offer_letters', label: 'Offers' },
]

const OFFER_SOURCE_OPTIONS = [
  { value: '', label: '—' },
  { value: 'Drive', label: 'Drive' },
  { value: 'WhatsApp', label: 'WhatsApp' },
  { value: 'Promotions', label: 'Promotions' },
  { value: 'Interview slots', label: 'Interview slots' },
  { value: 'Shared', label: 'Shared' },
  { value: 'Template', label: 'Template' },
  { value: 'Other', label: 'Other' },
]

const OFFER_PERSIST_KEYS = new Set([
  'candidate',
  'company_name',
  'notes',
  'source',
  'handler',
  'filename',
  'date_modified',
  'file_url',
  'drive_file_id',
  'folder_url',
])

const VAULT_SECTIONS = {
  service_accounts: {
    title: 'Service accounts',
    addLabel: 'Add account',
    fields: [
      { key: 'id', label: 'ID', required: true },
      { key: 'label', label: 'Label' },
      { key: 'service', label: 'Service' },
      { key: 'username', label: 'Username' },
      { key: 'password', label: 'Password' },
      { key: 'notes', label: 'Notes', textarea: true },
    ],
  },
  prompts: {
    title: 'Prompts',
    addLabel: 'Add prompt',
    fields: [
      { key: 'id', label: 'ID', required: true },
      { key: 'title', label: 'Title' },
      { key: 'source', label: 'Source' },
      { key: 'body', label: 'Body', textarea: true, full: true },
    ],
  },
  resources: {
    title: 'Key links',
    addLabel: 'Add link',
    fields: [
      { key: 'id', label: 'ID', required: true },
      { key: 'title', label: 'Title' },
      { key: 'url', label: 'URL' },
      { key: 'notes', label: 'Notes', textarea: true },
    ],
  },
  offer_letters: {
    title: 'Offer letters',
    addLabel: 'Add offer',
    fields: [
      { key: 'id', label: 'ID', required: true },
      { key: 'candidate', label: 'Candidate' },
      { key: 'company_name', label: 'Company name' },
      {
        key: 'source',
        label: 'Source',
        select: true,
        options: OFFER_SOURCE_OPTIONS,
      },
      { key: 'handler', label: 'Handler / shared by' },
      { key: 'notes', label: 'Notes', textarea: true, full: true },
      { key: 'filename', label: 'Filename', full: true },
      { key: 'date_modified', label: 'Date modified' },
      { key: 'size_kb', label: 'Size (KB)', type: 'number' },
      { key: 'drive_file_id', label: 'Drive file ID', placeholder: '1abc… for direct preview' },
      { key: 'file_url', label: 'View URL (Drive file link)', full: true },
      { key: 'folder_url', label: 'Folder URL', full: true },
    ],
  },
}

function offerCompanyName(row) {
  return String(row?.company_name || '').trim()
}

function offerNotes(row) {
  return String(row?.notes || '').trim()
}

function truncateText(text, max = 56) {
  const value = String(text || '').trim()
  if (!value) return ''
  return value.length <= max ? value : `${value.slice(0, max - 1)}…`
}

function offerPdfStatus(row) {
  return row?.drive_file_id || row?.file_url ? 'ready' : 'missing'
}

function emptyForm(section) {
  const cfg = VAULT_SECTIONS[section]
  const form = {}
  for (const f of cfg?.fields || []) {
    form[f.key] = ''
  }
  return form
}

function rowToForm(section, row) {
  const form = emptyForm(section)
  for (const key of Object.keys(form)) {
    const val = row?.[key]
    form[key] = val != null ? String(val) : ''
  }
  return form
}

function formToPayload(section, form) {
  const cfg = VAULT_SECTIONS[section]
  const payload = {}
  const persistKeys = section === 'offer_letters' ? OFFER_PERSIST_KEYS : null
  for (const f of cfg?.fields || []) {
    const raw = String(form[f.key] ?? '').trim()
    if (f.key === 'id') {
      payload.id = raw
    } else if (f.type === 'number') {
      if (raw) payload[f.key] = Number(raw)
    } else if (persistKeys?.has(f.key)) {
      payload[f.key] = raw
    } else if (raw) {
      payload[f.key] = raw
    }
  }
  return payload
}

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

function VaultBlockHead({ title, onAdd, addLabel }) {
  return (
    <div className="dr-vault-block-head">
      <h3 className="dr-vault-subtitle">{title}</h3>
      <button type="button" className="cand-btn cand-btn--sm" onClick={onAdd}>
        {addLabel}
      </button>
    </div>
  )
}

function RowActions({ onView, onEdit, onDelete }) {
  return (
    <div className="dr-row-actions">
      {onView && (
        <button type="button" className="cand-btn cand-btn--sm cand-btn--ghost" onClick={onView}>
          View
        </button>
      )}
      <button type="button" className="cand-btn cand-btn--sm" onClick={onEdit}>
        Edit
      </button>
      <button type="button" className="cand-btn cand-btn--sm cand-btn--danger" onClick={onDelete}>
        Delete
      </button>
    </div>
  )
}

function OfferLetterPreviewModal({ row, offerFolder, onClose }) {
  const drive = offerLetterPreviewEmbed(row, offerFolder)
  const previewUrl = offerLetterPreviewApiUrl(row, API)
  const downloadUrl = row?.id
    ? `${API}/data-room/offer-letters/${encodeURIComponent(row.id)}/download`
    : null
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState('')
  const [previewKey, setPreviewKey] = useState(0)
  const fileInputRef = useRef(null)

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  async function onUploadPdf(file) {
    if (!file || !row?.id) return
    setUploading(true)
    setUploadError('')
    try {
      const body = new FormData()
      body.append('file', file)
      const res = await fetch(`${API}/data-room/offer-letters/${encodeURIComponent(row.id)}/upload`, {
        method: 'POST',
        credentials: 'include',
        body,
      })
      const data = await res.json()
      if (!res.ok || data.status !== 'ok') {
        throw new Error(data.message || `Upload failed (${res.status})`)
      }
      setPreviewKey(k => k + 1)
    } catch (err) {
      setUploadError(err.message || 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div
      className="dr-offer-preview"
      role="presentation"
      onClick={onClose}
    >
      <div
        className="dr-offer-preview-panel dr-offer-preview-panel--pdf"
        role="dialog"
        aria-labelledby="dr-offer-preview-title"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          className="dr-offer-preview-close"
          onClick={onClose}
          aria-label="Close preview"
        >
          ×
        </button>
        <header className="dr-offer-preview-head">
          <h3 id="dr-offer-preview-title" className="dr-offer-preview-title">
            {row.filename || row.id}
          </h3>
          {row.candidate && <p className="dr-muted">{row.candidate}</p>}
        </header>
        <div className="dr-offer-preview-body">
          {previewUrl ? (
            <PdfPreviewPane
              key={previewKey}
              src={previewUrl}
              title={row.filename || 'Offer letter'}
              className="dr-offer-preview-pdf"
            />
          ) : (
            <p className="dr-offer-preview-empty">
              No preview available for this entry.
            </p>
          )}
        </div>
        <footer className="dr-offer-preview-foot">
          <div className="dr-offer-preview-foot__left">
            {uploadError && (
              <p className="dr-offer-preview-error" role="alert">{uploadError}</p>
            )}
            {!row.drive_file_id && drive.mode === 'missing' && (
              <p className="dr-muted dr-offer-preview-hint">
                No Drive file ID — upload the PDF here or add one in Edit.
              </p>
            )}
          </div>
          <div className="dr-offer-preview-foot__actions">
            <input
              ref={fileInputRef}
              type="file"
              accept="application/pdf,.pdf"
              hidden
              onChange={(e) => {
                const f = e.target.files?.[0]
                if (f) onUploadPdf(f)
                e.target.value = ''
              }}
            />
            <button
              type="button"
              className="cand-btn cand-btn--sm cand-btn--primary"
              disabled={uploading}
              onClick={() => fileInputRef.current?.click()}
            >
              {uploading ? 'Uploading…' : 'Upload PDF'}
            </button>
            {downloadUrl && (
              <a
                href={downloadUrl}
                className="cand-btn cand-btn--sm cand-btn--ghost"
                download={row.filename || 'offer-letter.pdf'}
              >
                Download
              </a>
            )}
            <a
              href={drive.openUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="cand-btn cand-btn--sm cand-btn--ghost"
            >
              Open in Drive
            </a>
          </div>
        </footer>
      </div>
    </div>
  )
}

export function DataRoomVaultSection({ creds, active = true, onCredentialsChange, onError }) {
  const { confirm } = useConfirm()
  const [activeKey, setActiveKey] = useState(null)
  const [editor, setEditor] = useState(null)
  const [saving, setSaving] = useState(false)
  const [previewOffer, setPreviewOffer] = useState(null)
  const [vaultTab, setVaultTab] = useState('service_accounts')

  const onCopy = useCallback(async (key, text) => {
    const ok = await copyToClipboard(text)
    setActiveKey(ok ? key : null)
    if (ok) window.setTimeout(() => setActiveKey(k => (k === key ? null : k)), 1600)
  }, [])

  const openCreate = (section) => {
    setVaultTab(section)
    setEditor({ section, mode: 'create', itemId: null, form: emptyForm(section) })
  }

  const openEdit = (section, row) => {
    setEditor({
      section,
      mode: 'edit',
      itemId: row.id,
      form: rowToForm(section, row),
    })
  }

  const saveEditor = async () => {
    if (!editor || saving) return
    setSaving(true)
    onError?.('')
    try {
      const payload = formToPayload(editor.section, editor.form)
      if (!payload.id) {
        onError?.('ID is required')
        return
      }
      const updated =
        editor.mode === 'create'
          ? await createVaultItem(editor.section, payload)
          : await updateVaultItem(editor.section, editor.itemId, payload)
      onCredentialsChange?.(updated)
      setEditor(null)
    } catch (e) {
      onError?.(e.message || 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const removeItem = async (section, row) => {
    const label =
      row.label || row.title || row.filename || row.id || 'this entry'
    const ok = await confirm({
      title: 'Remove vault entry?',
      message: `Delete "${label}" from ${VAULT_SECTIONS[section]?.title || section}?`,
      confirmLabel: 'Delete',
      variant: 'danger',
    })
    if (!ok) return
    onError?.('')
    try {
      const updated = await deleteVaultItem(section, row.id)
      onCredentialsChange?.(updated)
    } catch (e) {
      onError?.(e.message || 'Delete failed')
    }
  }

  if (!creds) return null

  const accounts = creds.service_accounts || []
  const prompts = creds.prompts || []
  const resources = creds.resources || []
  const offers = creds.offer_letters || []
  const offerFolder =
    offers.find(row => row.folder_url)?.folder_url || DEFAULT_OFFER_FOLDER
  const sectionCfg = editor ? VAULT_SECTIONS[editor.section] : null

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

      <div className="dr-vault-stats dr-vault-stats--tabs" role="tablist" aria-label="Vault sections">
        {VAULT_TABS.map((tab) => {
          const count =
            tab.id === 'service_accounts' ? accounts.length
              : tab.id === 'prompts' ? prompts.length
                : tab.id === 'resources' ? resources.length
                  : offers.length
          const isActive = vaultTab === tab.id
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={isActive}
              className={`dr-vault-stat dr-vault-stat--tab${isActive ? ' dr-vault-stat--active' : ''}`}
              onClick={() => setVaultTab(tab.id)}
            >
              <div className="dr-vault-stat-label">{tab.label}</div>
              <div className="dr-vault-stat-value">{count}</div>
            </button>
          )
        })}
      </div>

      {vaultTab === 'service_accounts' && (
      <div className="dr-vault-block">
        <VaultBlockHead
          title="Service accounts"
          addLabel={VAULT_SECTIONS.service_accounts.addLabel}
          onAdd={() => openCreate('service_accounts')}
        />
        {accounts.length === 0 ? (
          <p className="dr-muted">No service accounts yet.</p>
        ) : (
          <div className="dr-svc-grid">
            {accounts.map(row => {
              const tone = serviceCardTone(row)
              const copyAll = [
                row.label || row.id,
                row.service ? `Service: ${row.service}` : '',
                row.username ? `Username: ${row.username}` : '',
                row.password ? `Password: ${row.password}` : '',
                row.notes || '',
              ]
                .filter(Boolean)
                .join('\n')
              return (
                <article className={`dr-svc-card dr-svc-card--${tone}`} key={row.id}>
                  <div className="dr-svc-card-head">
                    <div>
                      <h4 className="dr-svc-card-title">{row.label || row.id}</h4>
                      {row.service && <div className="dr-svc-service">{row.service}</div>}
                    </div>
                    <div className="dr-vault-actions">
                      {tone === 'current' && (
                        <span className="dr-svc-badge dr-svc-badge--current">Current</span>
                      )}
                      {tone === 'deprecated' && (
                        <span className="dr-svc-badge dr-svc-badge--deprecated">Old</span>
                      )}
                      <RowActions
                        onEdit={() => openEdit('service_accounts', row)}
                        onDelete={() => removeItem('service_accounts', row)}
                      />
                    </div>
                  </div>
                  {row.username && (
                    <div className="dr-svc-field">
                      <span className="dr-svc-field-label">Username</span>
                      <div className="dr-svc-field-value">
                        <code>{row.username}</code>
                        <CopyChip
                          label="Copy"
                          text={row.username}
                          copyKey={`${row.id}-user`}
                          activeKey={activeKey}
                          onCopy={onCopy}
                        />
                      </div>
                    </div>
                  )}
                  {row.password && (
                    <div className="dr-svc-field">
                      <span className="dr-svc-field-label">Password</span>
                      <div className="dr-svc-field-value">
                        <code className="dr-creds-pass">{row.password}</code>
                        <CopyChip
                          label="Copy"
                          text={row.password}
                          copyKey={`${row.id}-pass`}
                          activeKey={activeKey}
                          onCopy={onCopy}
                        />
                      </div>
                    </div>
                  )}
                  {row.notes && <p className="dr-svc-notes">{row.notes}</p>}
                  <div className="dr-svc-card-actions">
                    <CopyChip
                      label="Copy all"
                      text={copyAll}
                      copyKey={`${row.id}-all`}
                      activeKey={activeKey}
                      onCopy={onCopy}
                    />
                  </div>
                </article>
              )
            })}
          </div>
        )}
      </div>
      )}

      {vaultTab === 'prompts' && (
      <div className="dr-vault-block">
        <VaultBlockHead
          title="Prompts"
          addLabel={VAULT_SECTIONS.prompts.addLabel}
          onAdd={() => openCreate('prompts')}
        />
        {prompts.length === 0 ? (
          <p className="dr-muted">No prompts yet.</p>
        ) : (
          <div className="dr-prompt-list">
            {prompts.map(row => (
              <details className="dr-prompt-card" key={row.id}>
                <summary>
                  <span className="dr-prompt-card-title">{row.title || row.id}</span>
                  <span className="dr-prompt-card-meta">{(row.body || '').length} chars</span>
                  <span className="dr-prompt-card-actions" onClick={(e) => e.preventDefault()}>
                    <RowActions
                      onEdit={() => openEdit('prompts', row)}
                      onDelete={() => removeItem('prompts', row)}
                    />
                  </span>
                </summary>
                <div className="dr-prompt-body-wrap">
                  {row.source && <p className="dr-muted">{row.source}</p>}
                  <pre className="dr-prompt-body">{row.body}</pre>
                  <CopyChip
                    label="Copy prompt"
                    text={row.body || ''}
                    copyKey={`prompt-${row.id}`}
                    activeKey={activeKey}
                    onCopy={onCopy}
                  />
                </div>
              </details>
            ))}
          </div>
        )}
      </div>
      )}

      {vaultTab === 'offer_letters' && (
      <div className="dr-vault-block">
        <VaultBlockHead
          title="Offer letters"
          addLabel={VAULT_SECTIONS.offer_letters.addLabel}
          onAdd={() => openCreate('offer_letters')}
        />
        <p className="dr-muted dr-offer-folder">
          Drive folder:{' '}
          <a href={offerFolder} target="_blank" rel="noopener noreferrer">
            Offer letters for proof
          </a>
        </p>
        {offers.length === 0 ? (
          <p className="dr-muted">No offer letters catalogued yet.</p>
        ) : (
          <div className="cand-table-wrap">
            <table className="cand-table dr-table dr-offer-table">
              <thead>
                <tr>
                  <th>Candidate</th>
                  <th>Company</th>
                  <th>Source</th>
                  <th>Handler</th>
                  <th>Notes</th>
                  <th>Modified</th>
                  <th>PDF</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {offers.map(row => {
                  const openView = () => setPreviewOffer(row)
                  const notes = offerNotes(row)
                  const pdfStatus = offerPdfStatus(row)
                  return (
                  <tr key={row.id}>
                    <td data-label="Candidate">
                      <button
                        type="button"
                        className="dr-offer-candidate dr-offer-filename--link"
                        onClick={openView}
                        title={`Preview ${row.filename || row.id}`}
                      >
                        {row.candidate || '—'}
                      </button>
                      {row.filename && (
                        <div className="dr-offer-file-mini" title={row.filename}>
                          {truncateText(row.filename, 42)}
                        </div>
                      )}
                    </td>
                    <td data-label="Company" className="dr-offer-company">
                      {offerCompanyName(row) || '—'}
                    </td>
                    <td data-label="Source">{row.source || '—'}</td>
                    <td data-label="Handler">{row.handler || '—'}</td>
                    <td data-label="Notes" className="dr-summary dr-offer-notes" title={notes}>
                      {truncateText(notes) || '—'}
                    </td>
                    <td data-label="Modified">{row.date_modified || '—'}</td>
                    <td data-label="PDF">
                      <span className={`dr-offer-pdf dr-offer-pdf--${pdfStatus}`}>
                        {pdfStatus === 'ready' ? 'Ready' : 'Missing'}
                      </span>
                    </td>
                    <td className="dr-actions">
                      <RowActions
                        onView={openView}
                        onEdit={() => openEdit('offer_letters', row)}
                        onDelete={() => removeItem('offer_letters', row)}
                      />
                    </td>
                  </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
      )}

      {vaultTab === 'resources' && (
      <div className="dr-vault-block">
        <VaultBlockHead
          title="Key links"
          addLabel={VAULT_SECTIONS.resources.addLabel}
          onAdd={() => openCreate('resources')}
        />
        {resources.length === 0 ? (
          <p className="dr-muted">No links yet.</p>
        ) : (
          <ul className="dr-resource-grid">
            {resources.map(row => (
              <li className="dr-resource-card" key={row.id}>
                <div className="dr-resource-card-head">
                  <a
                    className="dr-resource-card-title"
                    href={row.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    title={row.title || row.url}
                  >
                    {row.title || row.url}
                  </a>
                  <RowActions
                    onEdit={() => openEdit('resources', row)}
                    onDelete={() => removeItem('resources', row)}
                  />
                </div>
                {row.notes && <p className="dr-resource-notes">{row.notes}</p>}
              </li>
            ))}
          </ul>
        )}
      </div>
      )}

      {previewOffer && (
        <OfferLetterPreviewModal
          row={previewOffer}
          offerFolder={offerFolder}
          onClose={() => setPreviewOffer(null)}
        />
      )}

      {editor && sectionCfg && (
        <div className="dr-modal-backdrop" role="presentation" onClick={() => setEditor(null)}>
          <div
            className="dr-modal cand-card"
            role="dialog"
            aria-labelledby="dr-vault-modal-title"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="dr-vault-modal-title" className="cand-title">
              {editor.mode === 'create' ? sectionCfg.addLabel : `Edit ${sectionCfg.title.toLowerCase()}`}
            </h2>
            <div className="dr-form-grid">
              {sectionCfg.fields.map((field) => (
                <label
                  key={field.key}
                  className={field.full ? 'dr-form-full' : undefined}
                >
                  {field.label}
                  {field.select ? (
                    <select
                      className="cand-input"
                      value={editor.form[field.key]}
                      onChange={(e) =>
                        setEditor((s) => ({
                          ...s,
                          form: { ...s.form, [field.key]: e.target.value },
                        }))
                      }
                    >
                      {(field.options || []).map((opt) => (
                        <option key={opt.value || 'empty'} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                  ) : field.textarea ? (
                    <textarea
                      className="cand-input"
                      rows={field.key === 'body' ? 8 : 3}
                      value={editor.form[field.key]}
                      readOnly={editor.mode === 'edit' && field.key === 'id'}
                      onChange={(e) =>
                        setEditor((s) => ({
                          ...s,
                          form: { ...s.form, [field.key]: e.target.value },
                        }))
                      }
                    />
                  ) : (
                    <input
                      className="cand-input"
                      type={field.type || 'text'}
                      value={editor.form[field.key]}
                      readOnly={editor.mode === 'edit' && field.key === 'id'}
                      onChange={(e) =>
                        setEditor((s) => ({
                          ...s,
                          form: { ...s.form, [field.key]: e.target.value },
                        }))
                      }
                    />
                  )}
                </label>
              ))}
            </div>
            <div className="dr-modal-actions">
              <button type="button" className="cand-btn" onClick={() => setEditor(null)} disabled={saving}>
                Cancel
              </button>
              <button
                type="button"
                className="cand-btn cand-btn--primary"
                onClick={saveEditor}
                disabled={saving}
              >
                {saving ? 'Saving…' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
