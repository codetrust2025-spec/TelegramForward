import React from 'react'

export function ReplyQuoteBar({ message, onClear }) {
  if (!message) return null
  const preview = (message.text || message.summary || '').trim().slice(0, 120)
  return (
    <div className="reply-quote-bar" role="status">
      <div className="reply-quote-bar__body">
        <span className="reply-quote-bar__label">Replying to</span>
        <span className="reply-quote-bar__text">{preview || 'Message'}</span>
      </div>
      <button type="button" className="reply-quote-bar__clear" onClick={onClear} aria-label="Cancel reply">
        ×
      </button>
    </div>
  )
}
