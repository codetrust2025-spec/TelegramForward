import React, { useMemo, useState } from 'react'
import { API } from '../config.js'
import { SegmentedControl } from './ui/SegmentedControl.jsx'
import { isCampaignEnabled, isForwardingEnabled } from '../utils/accountUi.js'

const MODE_OPTIONS = [
  { value: 'campaign', label: 'Campaign' },
  { value: 'forwarding', label: 'Forwarding' },
]

function activeMode(campaignOn, forwardingOn) {
  if (forwardingOn) return 'forwarding'
  if (campaignOn) return 'campaign'
  return 'campaign'
}

/**
 * One-tap primary mode for an account (replaces hunting through filters + nested tabs).
 */
export function AccountModeSwitcher({
  slot,
  postingModeConfig,
  postingModes,
  accountStates,
  onUpdated,
  className = '',
}) {
  const cfg = postingModeConfig || postingModes?.[slot] || {}
  const campaignOn = isCampaignEnabled(accountStates, slot, postingModes || { [slot]: cfg })
  const forwardingOn = isForwardingEnabled(accountStates, slot, postingModes || { [slot]: cfg })
  const value = useMemo(() => activeMode(campaignOn, forwardingOn), [campaignOn, forwardingOn])

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function applyMode(next) {
    if (!slot || next === value) return
    let patch = {}
    if (next === 'campaign') {
      patch = { campaign_enabled: true, forwarding_enabled: false }
    } else if (next === 'forwarding') {
      patch = {
        campaign_enabled: false,
        forwarding_enabled: true,
        forward_dispatch: 'auto',
      }
    }

    setLoading(true)
    setError('')
    try {
      const res = await fetch(`${API}/account/${slot}/posting-mode`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(patch),
      })
      const data = await res.json()
      if (data.status === 'error') {
        setError(data.message || 'Could not update mode')
        return
      }
      onUpdated?.()
    } catch (e) {
      setError(e.message || 'Request failed')
    } finally {
      setLoading(false)
    }
  }

  if (!slot) {
    return (
      <p className={`stat-hint account-mode-switcher-hint${className ? ` ${className}` : ''}`}>
        Select an account to choose Campaign or Forwarding.
      </p>
    )
  }

  return (
    <div className={`account-mode-switcher${className ? ` ${className}` : ''}`}>
      <SegmentedControl
        className="account-mode-switcher__control"
        label="This account uses"
        options={MODE_OPTIONS.map(o => ({ ...o, disabled: loading }))}
        value={value}
        onChange={applyMode}
        role="tablist"
      />
      <p className="account-mode-switcher__help">
        <strong>1.</strong> Pick mode here · <strong>2.</strong> Press <strong>Start</strong> below · <strong>3.</strong> Set message if needed
      </p>
      {error && <p className="field-error account-mode-switcher__error">{error}</p>}
    </div>
  )
}
