import React from 'react'
import { accountLabel } from '../../utils/accountUi.js'
import { buildCallLink, callTypeLabel, formatCallScheduleTime } from '../../utils/calls.js'
import { slotTag } from '../../utils/inboxMessageUtils.js'
import { isBlockedLead, isSpamStatus } from '../../utils/crm.js'
import { getLeadScore, leadScoreLabel } from '../../utils/leadUx.js'
import { FollowUpControls } from './FollowUpControls.jsx'
import { NotesEditor } from './NotesEditor.jsx'
import { StatusDropdown } from './StatusDropdown.jsx'

function formatActivity(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString([], {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return '—'
  }
}

function leadScoreClass(score) {
  return `crm-lead-score crm-lead-score--${score || 'cold'}`
}

export function LeadDetailsPanel({
  selected,
  selectedConv,
  lead,
  scheduledCall,
  onStatusChange,
  notes,
  onNotesChange,
  onSaveNotes,
  onFollowUp2h,
  onFollowUpTomorrow,
  onScheduleCall,
  onCallNow,
  onUnblock,
  onStartCall,
  saving,
  followUpLoading,
}) {
  if (!selected) {
    return (
      <aside className="crm-lead-panel">
        <div className="empty-state crm-lead-empty">Select a chat to manage the lead.</div>
      </aside>
    )
  }

  const username = lead?.username || ''
  const name = lead?.name || String(selected.user_id)
  const isBlocked = isBlockedLead(lead)
  const isSpam = isBlocked || isSpamStatus(lead?.status)
  const call = scheduledCall || lead?.scheduled_call
  const link = buildCallLink(call)
  const score = getLeadScore(selectedConv || {
    crm_status: lead?.status,
    crm_blocked: lead?.crm_blocked,
    unread_count: 0,
    last_user_message_at: lead?.last_user_message_at,
    last_reply_time: lead?.last_reply_at,
    reply_handled_at: lead?.reply_handled_at,
    crm_last_user_message_at: lead?.last_user_message_at,
    crm_last_reply_at: lead?.last_reply_at,
  })

  return (
    <aside className="crm-lead-panel">
      <h3 className="crm-lead-panel-title">Lead details</h3>

      {!isSpam && (
        <section className="crm-lead-section crm-lead-call-actions crm-lead-call-actions--top">
          <button
            type="button"
            className="btn btn--call-now btn--block crm-call-now-btn--hero"
            onClick={() => onCallNow?.()}
            disabled={!lead || saving}
          >
            📞 Call Now
          </button>
        </section>
      )}

      <section className="crm-lead-section crm-lead-score-row">
        <span className="crm-field-label">Lead score</span>
        <span className={leadScoreClass(score)}>{leadScoreLabel(score)}</span>
      </section>

      <section className="crm-lead-section">
        <span className="crm-field-label">User info</span>
        <p className="crm-lead-name">{name}</p>
        {username && (
          <p className="crm-lead-meta">@{String(username).replace(/^@/, '')}</p>
        )}
        <p className="crm-lead-meta">User ID: {selected.user_id}</p>
        <p className="crm-lead-meta">
          Account: {accountLabel(selected.slot)} ({slotTag(selected.slot)})
        </p>
      </section>

      {isBlocked && (
        <section className="crm-lead-section crm-lead-blocked">
          <span className="crm-field-label">Block list</span>
          <p className="crm-lead-meta crm-blocked-notice">
            This lead is blocked and hidden from the main inbox. Chat history is kept.
          </p>
          <button
            type="button"
            className="btn btn--warn btn--block"
            onClick={() => onUnblock?.()}
            disabled={!lead || saving}
          >
            Unblock
          </button>
        </section>
      )}

      <section className="crm-lead-section">
        <span className="crm-field-label">Status</span>
        <StatusDropdown
          value={isBlocked ? 'spam' : (lead?.status || 'new')}
          onChange={onStatusChange}
          disabled={saving || isBlocked}
        />
      </section>

      {!isSpam && (
        <FollowUpControls
          onRemind2h={onFollowUp2h}
          onRemindTomorrow={onFollowUpTomorrow}
          loading={followUpLoading}
          disabled={!lead}
        />
      )}

      <NotesEditor
        value={notes}
        savedValue={lead?.notes ?? ''}
        onChange={onNotesChange}
        onSave={onSaveNotes}
        saving={saving}
        disabled={!lead}
      />

      {call?.status === 'scheduled' && (
        <section className="crm-lead-section crm-lead-call">
          <span className="crm-field-label">📞 Scheduled call</span>
          <dl className="crm-activity-dl">
            <dt>Next call</dt>
            <dd>{formatCallScheduleTime(call.scheduled_time)}</dd>
            <dt>Call type</dt>
            <dd>{callTypeLabel(call.call_type)}</dd>
            {call.notes && (
              <>
                <dt>Notes</dt>
                <dd>{call.notes}</dd>
              </>
            )}
          </dl>
          <button
            type="button"
            className="btn btn--primary btn--block crm-start-call-btn"
            onClick={() => onStartCall?.(call)}
            disabled={!link.can_open}
            title={link.label}
          >
            Start Call
          </button>
          {!link.can_open && (
            <p className="crm-lead-meta crm-call-hint">{link.label}</p>
          )}
        </section>
      )}

      {!isSpam && call?.status !== 'scheduled' && (
        <section className="crm-lead-section">
          <button
            type="button"
            className="btn btn--accent btn--block"
            onClick={() => onScheduleCall?.()}
            disabled={!lead || saving}
          >
            Schedule Call
          </button>
        </section>
      )}

      <section className="crm-lead-section crm-lead-activity">
        <span className="crm-field-label">Activity</span>
        <dl className="crm-activity-dl">
          <dt>First message</dt>
          <dd>{formatActivity(lead?.first_message_at || lead?.created_at)}</dd>
          <dt>Last reply (you)</dt>
          <dd>{formatActivity(lead?.last_reply_at)}</dd>
          <dt>Last contact</dt>
          <dd>{formatActivity(lead?.last_contact_time)}</dd>
          {lead?.reminder_timestamp && !isSpam && (
            <>
              <dt>Follow-up due</dt>
              <dd>{formatActivity(lead.reminder_timestamp)}</dd>
            </>
          )}
        </dl>
      </section>
    </aside>
  )
}
