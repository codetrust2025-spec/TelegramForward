import React, { useEffect, useRef } from 'react'
import { Button } from './ui/Button.jsx'

const ICONS = {
  danger: '⏹',
  warn: '⚠️',
  default: '❓',
}

export function ConfirmDialog({
  title,
  message,
  details = [],
  variant = 'default',
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  onConfirm,
  onCancel,
}) {
  const cancelRef = useRef(null)

  useEffect(() => {
    cancelRef.current?.focus()
    function onKey(e) {
      if (e.key === 'Escape') onCancel()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onCancel])

  return (
    <div className="modal-backdrop confirm-backdrop" onClick={onCancel} role="presentation">
      <div
        className={`confirm-card confirm-card--${variant}`}
        onClick={(e) => e.stopPropagation()}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        aria-describedby="confirm-dialog-desc"
      >
        <div className={`confirm-card-icon confirm-card-icon--${variant}`} aria-hidden>
          {ICONS[variant] || ICONS.default}
        </div>
        <h2 id="confirm-dialog-title" className="confirm-card-title">
          {title}
        </h2>
        {message && (
          <p id="confirm-dialog-desc" className="confirm-card-message">
            {message}
          </p>
        )}
        {details.length > 0 && (
          <ul className="confirm-card-details">
            {details.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        )}
        <div className="confirm-card-actions">
          <Button variant="ghost" ref={cancelRef} onClick={onCancel}>
            {cancelLabel}
          </Button>
          <Button
            variant={variant === 'danger' ? 'danger' : variant === 'warn' ? 'warning' : 'primary'}
            onClick={onConfirm}
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  )
}
