import React, { useEffect, useRef } from 'react'

export function MessageActionMenu({
  open,
  x,
  y,
  out,
  showReactions,
  canReply,
  canCopy,
  canEdit,
  canDelete,
  canPin,
  isPinned,
  onClose,
  onReply,
  onCopy,
  onEdit,
  onDelete,
  onPin,
  onForward,
  onReact,
}) {
  const ref = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    function onDoc(e) {
      if (ref.current && !ref.current.contains(e.target)) onClose?.()
    }
    function onKey(e) {
      if (e.key === 'Escape') onClose?.()
    }
    document.addEventListener('mousedown', onDoc)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDoc)
      document.removeEventListener('keydown', onKey)
    }
  }, [open, onClose])

  if (!open) return null

  const items = [
    canReply && { label: 'Reply', action: onReply },
    canCopy && { label: 'Copy', action: onCopy },
    canEdit && { label: 'Edit', action: onEdit },
    canPin && { label: isPinned ? 'Unpin' : 'Pin', action: onPin },
    onForward && { label: 'Forward', action: onForward },
    canDelete && { label: 'Delete', action: onDelete, danger: true },
  ].filter(Boolean)

  return (
    <div
      ref={ref}
      className="message-action-menu"
      style={{ left: x, top: y }}
      role="menu"
    >
      {showReactions && (
        <div className="message-action-menu__reactions" role="group" aria-label="Reactions">
          {['👍', '❤️', '😂', '🔥'].map(emoji => (
            <button
              key={emoji}
              type="button"
              className="message-action-menu__react"
              onClick={() => {
                onReact?.(emoji)
                onClose?.()
              }}
            >
              {emoji}
            </button>
          ))}
        </div>
      )}
      {items.map(item => (
        <button
          key={item.label}
          type="button"
          role="menuitem"
          className={`message-action-menu__item${item.danger ? ' message-action-menu__item--danger' : ''}`}
          onClick={() => {
            item.action?.()
            onClose?.()
          }}
        >
          {item.label}
        </button>
      ))}
    </div>
  )
}
