import React, { useMemo } from 'react'
import { ButtonContent } from '../../Loader.jsx'
import { accountLabel } from '../../utils/accountUi.js'
import { CallScheduledBanner } from './CallScheduledBanner.jsx'
import { isBlockedLead } from '../../utils/crm.js'
import { getReplyAlertLevel, unansweredElapsedMs } from '../../utils/replyAlert.js'
import {
  getDynamicQuickReplies,
  formatWaitingLabel,
} from '../../utils/leadUx.js'
import { countInbound, formatInboxTime, lastInboundMessage } from '../../utils/inboxMessageUtils.js'
import { MessageStatus } from './MessageStatus.jsx'

function formatWaitingSince(conv) {
  if (!conv) return null
  const ms = unansweredElapsedMs(conv)
  if (ms == null) return null
  const mins = Math.max(1, Math.floor(ms / 60000))
  return `Waiting since: ${mins} min${mins === 1 ? '' : 's'}`
}

export function ChatWindow({
  selected,
  selectedConv,
  messages,
  loadingMessages,
  replyText,
  onReplyChange,
  onSend,
  sending,
  error,
  showNewMessages,
  onJumpToLatest,
  onJumpToInbound,
  messagesScrollRef,
  onMessagesScroll,
  messagesEndRef,
  onQuickReply,
  onScheduleCall,
  onCallNow,
  onMarkSpam,
  onMarkHandled,
  crmSaving,
  scheduledCall,
}) {
  const quickReplies = useMemo(
    () => getDynamicQuickReplies(selectedConv?.crm_status),
    [selectedConv?.crm_status],
  )

  if (!selected) {
    return (
      <section className="crm-chat-window inbox-chat-panel">
        <div className="empty-state inbox-chat-empty">Select a lead to view the conversation.</div>
      </section>
    )
  }

  const blocked = isBlockedLead(selectedConv)
  const replyAlertLevel = getReplyAlertLevel(selectedConv)
  const inboundCount = countInbound(messages)
  const lastInbound = lastInboundMessage(messages)
  const lastVisibleIsOutbound = messages.length > 0 && messages[messages.length - 1]?.direction === 'out'
  const showScrollForInbound = !loadingMessages && inboundCount > 0 && lastVisibleIsOutbound
  const lastMsgAt = selectedConv?.last_message_at
  const waitingSince = formatWaitingSince(selectedConv)
  const charCount = replyText.length

  return (
    <section className="crm-chat-window inbox-chat-panel">
      <header className="inbox-chat-header">
        <div className="inbox-chat-header-main">
          <strong>{selectedConv?.name || selectedConv?.username || selected.user_id}</strong>
          <span className="inbox-chat-header-meta">
            {selectedConv?.username && `@${String(selectedConv.username).replace(/^@/, '')} · `}
            via {accountLabel(selected.slot)}
          </span>
        </div>
        <div className="inbox-chat-header-actions">
          {!blocked && replyAlertLevel && (
            <button
              type="button"
              className="btn btn--warn btn--sm"
              onClick={onMarkHandled}
              disabled={crmSaving}
              title="Stop buzzer without sending a message"
            >
              Mark handled
            </button>
          )}
          {!blocked && (
            <button
              type="button"
              className="btn btn--ghost btn--sm crm-mark-spam-btn"
              onClick={onMarkSpam}
              disabled={crmSaving}
              title="Block lead — moves to Spam / Blocked"
            >
              Mark as Spam
            </button>
          )}
        </div>
      </header>

      {(lastMsgAt || waitingSince) && (
        <div className="crm-chat-meta-bar" role="status">
          {lastMsgAt && (
            <span className="crm-chat-meta-item">
              Last message: <time>{formatInboxTime(lastMsgAt)}</time>
            </span>
          )}
          {waitingSince && (
            <span className="crm-chat-meta-item crm-chat-meta-item--waiting">
              {waitingSince}
            </span>
          )}
        </div>
      )}

      {replyAlertLevel && !blocked && (
        <div className={`crm-reply-alert-banner crm-reply-alert-banner--${replyAlertLevel}`} role="status">
          {replyAlertLevel === 'aggressive'
            ? '⚠ No reply for 20+ minutes — urgent'
            : replyAlertLevel === 'buzzer'
              ? 'No reply for 10+ minutes — buzzer active'
              : 'No reply for 5+ minutes — respond soon'}
        </div>
      )}

      <CallScheduledBanner call={scheduledCall || selectedConv?.crm_scheduled_call} />

      {showScrollForInbound && lastInbound && (
        <div className="crm-inbound-hint" role="status">
          <span>
            Candidate sent {inboundCount} message{inboundCount === 1 ? '' : 's'} — latest: “
            {(lastInbound.text || '').slice(0, 80)}
            ” ({formatInboxTime(lastInbound.timestamp)}).
          </span>
          <button
            type="button"
            className="btn btn--ghost btn--sm"
            onClick={onJumpToInbound}
          >
            Show candidate messages
          </button>
        </div>
      )}

      <div className="inbox-chat-messages-wrap">
        {showNewMessages && (
          <button
            type="button"
            className="inbox-new-messages-pill"
            onClick={onJumpToLatest}
            aria-label="Scroll to new messages"
          >
            ⬇ New messages
          </button>
        )}
        <div
          className="inbox-messages chat-container"
          ref={messagesScrollRef}
          onScroll={onMessagesScroll}
          role="log"
          aria-live="polite"
        >
          <div className="inbox-messages-inner">
            {loadingMessages && <div className="empty-state">Loading…</div>}
            {!loadingMessages && messages.length === 0 && (
              <div className="empty-state">No messages stored yet.</div>
            )}
            {!loadingMessages && messages.map((m, i) => {
              if (m.direction === 'system') {
                return (
                  <div key={`${m.id}-${i}`} className="inbox-system-message" role="status">
                    {m.text}
                  </div>
                )
              }
              return (
                <div
                  key={`${m.id}-${i}`}
                  className={`inbox-bubble inbox-bubble--${m.direction === 'out' ? 'out' : 'in'}${m.status === 'failed' ? ' inbox-bubble--failed' : ''}${m.status === 'sending' ? ' inbox-bubble--sending' : ''}`}
                >
                  <div className="inbox-bubble-text">{m.text || (m.media ? '[media]' : '')}</div>
                  <div className="inbox-bubble-meta">
                    <time>{formatInboxTime(m.timestamp)}</time>
                    <MessageStatus
                      direction={m.direction}
                      status={m.status || (m.direction === 'out' ? 'delivered' : 'received')}
                    />
                  </div>
                </div>
              )
            })}
            <div className="inbox-messages-anchor" ref={messagesEndRef} aria-hidden />
          </div>
        </div>
      </div>

      {blocked && (
        <div className="crm-blocked-compose-notice" role="status">
          Lead is blocked — replies disabled. Unblock from the right panel to interact again.
        </div>
      )}

      <footer className="inbox-compose reply-box crm-compose">
        {error && <p className="inbox-error inbox-error--compose" role="alert">{error}</p>}

        {!blocked && (
          <div className="crm-compose-actions">
            <div className="crm-compose-primary">
              <button
                type="button"
                className="btn btn--call-now crm-call-now-btn--hero"
                onClick={() => typeof onCallNow === 'function' && onCallNow()}
                disabled={crmSaving}
                title="Start a live call now"
              >
                📞 Call Now
              </button>
              <button
                type="button"
                className="btn btn--primary crm-send-btn"
                onClick={onSend}
                disabled={sending || !replyText.trim()}
              >
                <ButtonContent loading={sending} loadingLabel="Sending…">Send</ButtonContent>
              </button>
            </div>
            <div className="crm-compose-secondary">
              {quickReplies.map(q => (
                <button
                  key={q.id}
                  type="button"
                  className={`btn btn--sm btn--ghost crm-quick-chip${q.id === 'smart' ? ' crm-quick-chip--smart' : ''}`}
                  onClick={(e) => {
                    e.preventDefault()
                    e.stopPropagation()
                    if (q.action === 'schedule_call') {
                      if (typeof onScheduleCall === 'function') onScheduleCall()
                      return
                    }
                    if (q.text) onQuickReply(q.text)
                  }}
                  disabled={sending}
                >
                  {q.label}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="crm-compose-input-row">
          <textarea
            className="input input--textarea inbox-reply-input crm-reply-input"
            rows={4}
            placeholder={blocked ? 'Unblock to reply…' : 'Type reply… (Enter to send)'}
            value={replyText}
            onChange={e => onReplyChange(e.target.value)}
            disabled={blocked}
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                if (!sending && !blocked) onSend()
              }
            }}
          />
          {!blocked && charCount > 0 && (
            <span className="crm-char-count" aria-live="polite">{charCount}</span>
          )}
        </div>
      </footer>
    </section>
  )
}
