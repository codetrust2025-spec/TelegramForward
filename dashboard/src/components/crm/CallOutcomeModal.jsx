import React from 'react'

const OUTCOMES = [
  { id: 'interested', label: 'Interested' },
  { id: 'not_interested', label: 'Not Interested' },
  { id: 'follow_up', label: 'Follow-up' },
]

export function CallOutcomeModal({ open, leadName, onSelect, onDismiss, saving }) {
  if (!open) return null

  return (
    <div className="crm-modal-backdrop" role="presentation" onClick={onDismiss}>
      <div
        className="crm-modal crm-modal--compact"
        role="dialog"
        aria-labelledby="call-outcome-title"
        onClick={e => e.stopPropagation()}
      >
        <h3 id="call-outcome-title" className="crm-modal-title">Mark call outcome</h3>
        <p className="crm-modal-sub">
          Call time passed{leadName ? ` · ${leadName}` : ''}. How did it go?
        </p>
        <div className="crm-outcome-btns">
          {OUTCOMES.map(o => (
            <button
              key={o.id}
              type="button"
              className="btn btn--ghost btn--block"
              disabled={saving}
              onClick={() => onSelect(o.id)}
            >
              {o.label}
            </button>
          ))}
        </div>
        <button type="button" className="btn btn--ghost btn--sm crm-modal-skip" onClick={onDismiss} disabled={saving}>
          Skip for now
        </button>
      </div>
    </div>
  )
}
