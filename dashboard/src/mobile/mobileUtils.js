import {
  filterSlotsExcludingShutdown,
  getAccountStatus,
  isCampaignEnabled,
  isForwardingEnabled,
  sortAccountsForDisplay,
} from '../utils/accountUi.js'

/** Logged-in slots excluding shutdown list. */
export function activeFleetSlots(state, loggedInSlots) {
  return filterSlotsExcludingShutdown(
    loggedInSlots,
    state?.account_shutdown,
    state?.shutdown_list,
  )
}

export function isAccountActiveForModeFilter(acct, slot, state, postingModes, modeFilter) {
  if (modeFilter === 'forwarding') {
    return isForwardingEnabled(state?.account_states, slot, postingModes)
  }
  if (modeFilter === 'campaign') {
    return isCampaignEnabled(state?.account_states, slot, postingModes)
  }
  return true
}

export function includeSlotForModeFilter(modeFilter, accountStates, postingModes, slot) {
  if (modeFilter === 'forwarding') {
    return isForwardingEnabled(accountStates, slot, postingModes)
  }
  if (modeFilter === 'campaign') {
    return isCampaignEnabled(accountStates, slot, postingModes)
  }
  return true
}

export function sortedFleetSlots(state, loggedInSlots) {
  return sortAccountsForDisplay(
    activeFleetSlots(state, loggedInSlots),
    state?.account_states,
    state?.account_info,
  )
}

export function fleetSlotStatus(state, slot) {
  const acct = state?.account_states?.[slot]
  const loggedIn = !!state?.account_info?.[slot]
  return getAccountStatus(
    acct,
    loggedIn,
    state?.account_status?.[slot],
    state?.account_shutdown,
    slot,
  )
}
