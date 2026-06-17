import React, { useCallback, useState } from 'react'
import { copyToClipboard } from '../utils/copyToClipboard.js'

const DEFAULT_OFFER_FOLDER =
  'https://drive.google.com/drive/folders/1oHMisQJAudp-4RwAG_oMLsbPStd99g8B'

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

export function DataRoomVaultSection({ creds, active = true }) {
  const [activeKey, setActiveKey] = useState(null)

  const onCopy = useCallback(async (key, text) => {
    const ok = await copyToClipboard(text)
    setActiveKey(ok ? key : null)
    if (ok) window.setTimeout(() => setActiveKey(k => (k === key ? null : k)), 1600)
  }, [])

  if (!creds) return null

  const accounts = creds.service_accounts || []
  const prompts = creds.prompts || []
  const resources = creds.resources || []
  const offers = creds.offer_letters || []
  const offerFolder =
    offers.find(row => row.folder_url)?.folder_url || DEFAULT_OFFER_FOLDER

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

      <div className="dr-vault-block">
        <div className="dr-vault-block-head">
          <h3 className="dr-vault-subtitle">Service accounts</h3>
        </div>
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
                    {tone === 'current' && (
                      <span className="dr-svc-badge dr-svc-badge--current">Current</span>
                    )}
                    {tone === 'deprecated' && (
                      <span className="dr-svc-badge dr-svc-badge--deprecated">Old</span>
                    )}
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

      <div className="dr-vault-block">
        <div className="dr-vault-block-head">
          <h3 className="dr-vault-subtitle">Prompts</h3>
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

      <div className="dr-vault-block">
        <div className="dr-vault-block-head">
          <h3 className="dr-vault-subtitle">Offer letters</h3>
        </div>
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
                  <th>File</th>
                  <th>Candidate</th>
                  <th>Modified</th>
                  <th>Size</th>
                  <th>Notes</th>
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
                    <td data-label="Size">
                      {row.size_kb ? `${row.size_kb} KB` : '—'}
                    </td>
                    <td data-label="Notes" className="dr-summary" title={row.notes}>
                      {row.notes || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="dr-vault-block">
        <div className="dr-vault-block-head">
          <h3 className="dr-vault-subtitle">Key links</h3>
        </div>
        {resources.length === 0 ? (
          <p className="dr-muted">No links yet.</p>
        ) : (
          <ul className="dr-resource-grid">
            {resources.map(row => (
              <li className="dr-resource-card" key={row.id}>
                <a
                  className="dr-resource-card-title"
                  href={row.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  title={row.title || row.url}
                >
                  {row.title || row.url}
                </a>
                {row.notes && <p className="dr-resource-notes">{row.notes}</p>}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}
