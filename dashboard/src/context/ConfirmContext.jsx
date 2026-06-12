import React, { createContext, useCallback, useContext, useState } from 'react'
import { ConfirmDialog } from '../components/ConfirmDialog.jsx'

const GLOBAL_CTX_KEY = '__TA_CONFIRM_CONTEXT__'
const GLOBAL_VALUE_KEY = '__TA_CONFIRM_VALUE__'

function getConfirmContext() {
  if (typeof globalThis !== 'undefined' && globalThis[GLOBAL_CTX_KEY]) {
    return globalThis[GLOBAL_CTX_KEY]
  }
  const ctx = createContext(null)
  if (typeof globalThis !== 'undefined') {
    globalThis[GLOBAL_CTX_KEY] = ctx
  }
  return ctx
}

const ConfirmContext = getConfirmContext()

/**
 * @param {object} options
 * @param {string} options.title
 * @param {string} [options.message]
 * @param {string[]} [options.details]
 * @param {string[]} [options.cleared] — shown under “Will be reset to zero”
 * @param {string[]} [options.kept] — shown under “Not deleted”
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

  const value = { confirm }

  // TeleAutomation bundles duplicate React copies; inline useConfirm reads this global.
  // Do not clear on unmount — Strict Mode / remounts left __TA_CONFIRM_VALUE__ null and crashed the UI.
  if (typeof globalThis !== 'undefined') {
    globalThis[GLOBAL_VALUE_KEY] = value
  }

  return (
    <ConfirmContext.Provider value={value}>
      {children}
      {pending && (
        <ConfirmDialog
          title={pending.title}
          message={pending.message}
          details={pending.details}
          cleared={pending.cleared}
          kept={pending.kept}
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
  if (ctx) return ctx
  if (typeof globalThis !== 'undefined' && globalThis[GLOBAL_VALUE_KEY]) {
    return globalThis[GLOBAL_VALUE_KEY]
  }
  throw new Error('useConfirm must be used within ConfirmProvider')
}
