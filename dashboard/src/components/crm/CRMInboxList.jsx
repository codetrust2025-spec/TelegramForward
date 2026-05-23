import React, { useMemo } from 'react'
import { CRM_FILTERS, CRM_STATUS_SPAM, isBlockedLead, statusLabel } from '../../utils/crm.js'
import { formatAlertBanner, getReplyAlertLevel, replyAlertLabel } from '../../utils/replyAlert.js'
import {
  getLeadPriority,
  formatWaitingLabel,
  sortConversationsByUrgency,
} from '../../utils/leadUx.js'
import { formatInboxTime, slotTag } from '../../utils/inboxMessageUtils.js'

function statusClass(status) {
  const s = status || 'new'
  return `crm-status-tag crm-status-tag--${s}`
}

function priorityDotClass(priority) {
  if (priority === 'hot') return 'crm-priority-dot crm-priority-dot--hot'
  if (priority === 'warm') return 'crm-priority-dot crm-priority-dot--warm'
  if (priority === 'active') return 'crm-priority-dot crm-priority-dot--active'
  return 'crm-priority-dot crm-priority-dot--none'
}

export function CRMInboxList({
  conversations,
  selected,
  mode,
  filter,
  search,
  onFilterChange,
  onSearchChange,
  onSelect,
  alertCounts = null,
}) {
  const q = (search || '').trim().toLowerCase()

  const filtered = useMemo(() => {
    const list = conversations.filter(c => {
      const blocked = isBlockedLead(c)
      const st = blocked ? CRM_STATUS_SPAM : (c.crm_status || 'new')
      if (filter === 'spam') return blocked
      if (filter === 'unread') return (c.unread_count || 0) > 0 && !blocked
      if (filter === 'all') return !blocked
      if (filter === 'interested' || filter === 'follow_up' || filter === 'converted') {
        return st === filter && !blocked
      }
      return st === filter && !blocked
    }).filter(c => {
      if (!q) return true
      const hay = [
        c.name,
        c.username,
        String(c.user_id),
        c.last_message,
        c.account_id,
      ].join(' ').toLowerCase()
      return hay.includes(q)
    })
    return sortConversationsByUrgency(list)
  }, [conversations, filter, q])

  return (
    <aside className="crm-inbox-list inbox-list-panel">
      <div className="crm-inbox-list-tools">
        {alertCounts?.total > 0 && (
          <p className="crm-delayed-banner" role="status">
            {formatAlertBanner(alertCounts)}
          </p>
        )}
        <input
          type="search"
          className="input crm-search-input"
          placeholder="Search name or message…"
          value={search}
          onChange={e => onSearchChange(e.target.value)}
          aria-label="Search conversations"
        />
        <div className="crm-filter-chips" role="tablist" aria-label="Lead filters">
          {CRM_FILTERS.map(f => (
            <button
              key={f.id}
              type="button"
              role="tab"
              aria-selected={filter === f.id}
              className={`chip chip--sm${filter === f.id ? ' chip--active' : ''}`}
              onClick={() => onFilterChange(f.id)}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {filtered.length === 0 && (
        <div className="empty-state inbox-empty">No conversations match this filter.</div>
      )}

      {filtered.map(c => {
        const key = `${c.account_id}-${c.user_id}`
        const active = selected?.slot === c.account_id && Number(selected.user_id) === Number(c.user_id)
        const alertLevel = getReplyAlertLevel(c)
        const priority = getLeadPriority(c)
        const waitingLabel = formatWaitingLabel(c)
        const alertClass = alertLevel === 'aggressive'
          ? ' crm-conv-item--urgent'
          : alertLevel === 'buzzer'
            ? ' crm-conv-item--delayed'
            : alertLevel === 'soft'
              ? ' crm-conv-item--waiting'
              : ''
        return (
          <button
            key={key}
            type="button"
            className={`inbox-conv-item crm-conv-item${active ? ' inbox-conv-item--active' : ''}${c.crm_reminder_due && !isBlockedLead(c) ? ' crm-conv-item--due' : ''}${isBlockedLead(c) ? ' crm-conv-item--spam' : ''}${alertClass}`}
            onClick={() => onSelect(c)}
          >
            <span className={priorityDotClass(priority)} title={
              priority === 'hot' ? 'Urgent — waiting >10 min'
                : priority === 'warm' ? 'Follow-up / waiting'
                  : priority === 'active' ? 'Active lead'
                    : ''
            } aria-hidden />
            <div className="inbox-conv-item-top">
              <span className="inbox-conv-name">{c.name || c.username || c.user_id}</span>
              <span className="inbox-conv-tag">[{slotTag(c.account_id)}]</span>
              {waitingLabel ? (
                <span className="crm-waiting-time">{waitingLabel}</span>
              ) : (
                <span className="inbox-conv-time">{formatInboxTime(c.last_message_at)}</span>
              )}
            </div>
            <div className="inbox-conv-preview">{c.last_message || '—'}</div>
            <div className="crm-conv-item-footer">
              {alertLevel && !isBlockedLead(c) && (
                <span className={`crm-delayed-pill crm-delayed-pill--${alertLevel}`}>
                  {replyAlertLabel(alertLevel)}
                </span>
              )}
              {isBlockedLead(c) ? (
                <span className="crm-status-tag crm-status-tag--blocked">Blocked</span>
              ) : (
                <span className={statusClass(c.crm_status)}>{statusLabel(c.crm_status)}</span>
              )}
              {c.crm_reminder_due && !isBlockedLead(c) && (
                <span className="crm-reminder-pill">Due</span>
              )}
            </div>
            {c.unread_count > 0 && (
              <span className="inbox-unread-badge">{c.unread_count}</span>
            )}
          </button>
        )
      })}
    </aside>
  )
}
