import React from 'react'

export function FollowUpControls({ onRemind2h, onRemindTomorrow, loading, disabled }) {
  return (
    <div className="crm-follow-up">
      <span className="crm-field-label">Follow-up</span>
      <div className="crm-follow-up-btns">
        <button
          type="button"
          className="btn btn--ghost btn--sm crm-follow-up-btn crm-follow-up-btn--accent"
          onClick={onRemind2h}
          disabled={disabled || loading}
        >
          Remind in 2h
        </button>
        <button
          type="button"
          className="btn btn--ghost btn--sm crm-follow-up-btn"
          onClick={onRemindTomorrow}
          disabled={disabled || loading}
        >
          Remind tomorrow
        </button>
      </div>
    </div>
  )
}
