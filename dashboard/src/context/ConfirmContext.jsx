import React, { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { ConfirmDialog } from '../components/ConfirmDialog.jsx'

const ConfirmContext = createContext(null)

/**
 * @param {object} options
 * @param {string} options.title
 * @param {string} [options.message]
 * @param {string[]} [options.details]
 * @param {'danger'|'warn'|'default'} [options.variant]
 * @param {string} [options.confirmLabel]
 * @param {string} [options.cancelLabel]
 * @returns {Promise<boolean>}
 */
export function ConfirmProvider({ children }) {
  const [pending, setPending] = useState(null)

  const confirm = useCallback((options) => {
    return new Promise((resolve) => {
      setPending({ ...options, resolve })
    })
  }, [])

  const close = useCallback((result) => {
    setPending((prev) => {
      if (prev?.resolve) prev.resolve(result)
      return null
    })
  }, [])

  return (
    <ConfirmContext.Provider value={{ confirm }}>
      {children}
      {pending && (
        <ConfirmDialog
          title={pending.title}
          message={pending.message}
          details={pending.details}
          variant={pending.variant || 'default'}
          confirmLabel={pending.confirmLabel || 'Confirm'}
          cancelLabel={pending.cancelLabel || 'Cancel'}
          onConfirm={() => close(true)}
          onCancel={() => close(false)}
        />
      )}
    </ConfirmContext.Provider>
  )
}

export function useConfirm() {
  const ctx = useContext(ConfirmContext)
  if (!ctx) {
    throw new Error('useConfirm must be used within ConfirmProvider')
  }
  return ctx
}
