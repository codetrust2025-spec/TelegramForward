import React, { useState, useEffect, useRef, useMemo } from 'react'
import { ResizableDashboardLayout } from './ResizableDashboard.jsx'
import { ButtonContent, OverlayLoader, Spinner } from './Loader.jsx'
import { API, WS } from './config.js'
import { DashboardColumn } from './components/DashboardColumn.jsx'
import { AccountPanel } from './components/AccountPanel.jsx'
import { MessageEditor } from './components/MessageEditor.jsx'
import { GroupsUpload } from './components/GroupsUpload.jsx'
import { GroupsModal } from './components/GroupsModal.jsx'
import { GlobalActions } from './components/GlobalActions.jsx'
import { ProgressHubPanel } from './components/ProgressHubPanel.jsx'
import { aggregateFleetStats } from './utils/globalStats.js'
import {
  LogPanel,
  LogsToolbarTabs,
  LogToolbarActions,
} from './components/LogPanel.jsx'
import {
  accountLabel,
  formatJoinedStats,
  formatLogTime,
  getAccountSlots,
  getLoggedInSlots,
  isMembershipStale,
} from './utils/accountUi.js'
import { useConfirm } from './context/ConfirmContext.jsx'
import { InboxPanel } from './components/InboxPanel.jsx'
import { SoundQuietHoursToggle } from './components/SoundQuietHoursToggle.jsx'
import {
  playNewMessageSound,
  unlockNotificationSound,
  syncInboxAlertMusic,
  stopInboxAlertMusicOnUnmount,
  startIncomingCallRing,
  stopIncomingCallRing,
} from './utils/notificationSound.js'
import { IncomingCallModal } from './components/crm/IncomingCallModal.jsx'
import { computeInboxUnreadTotal, formatUnreadBadgeCount } from './utils/inboxUnread.js'
import { fetchCrmState } from './utils/crm.js'


function mergeInboxConversationList(convs, conversation, { clearUnread = false } = {}) {
  if (!conversation) return convs
  const uid = Number(conversation.user_id)
  const idx = convs.findIndex(c => Number(c.user_id) === uid)
  const row = {
    ...(idx >= 0 ? convs[idx] : {}),
    ...conversation,
    user_id: uid,
    ...(clearUnread ? { unread_count: 0 } : {}),
  }
  if (idx >= 0) convs[idx] = row
  else convs.unshift(row)
  convs.sort((a, b) => (b.last_message_at || '').localeCompare(a.last_message_at || ''))
  return convs
}

function mergeInboxWs(prev, data) {
  if (!data?.slot) return prev
  const slot = data.slot
  const next = { slots: { ...(prev?.slots || {}) } }
  if (data.inbox?.conversations) {
    next.slots[slot] = data.inbox
  } else if (prev?.slots?.[slot]) {
    next.slots[slot] = prev.slots[slot]
  } else {
    next.slots[slot] = { slot, conversations: [], updated_at: null }
  }
  const outboundEvents = new Set(['reply_sent', 'outgoing_message'])
  if ((data.event === 'new_message' || outboundEvents.has(data.event)) && data.conversation) {
    const convs = [...(next.slots[slot].conversations || [])]
    next.slots[slot] = {
      ...next.slots[slot],
      conversations: mergeInboxConversationList(convs, data.conversation, {
        clearUnread: outboundEvents.has(data.event),
      }),
    }
  }
  if (data.event === 'read' && data.conversation) {
    const convs = [...(next.slots[slot].conversations || [])]
    next.slots[slot] = {
      ...next.slots[slot],
      conversations: mergeInboxConversationList(convs, {
        ...data.conversation,
        unread_count: 0,
      }),
    }
  }
  return next
}


export default function App() {
  const [state, setState] = useState({
    running: false, total: 40, success: 0, failed: 0,
    current_group: '', success_list: [], failed_list: [],
    logs: [], message_id: null, cycle: 0,
    active_account: null, account_info: {}, custom_message: '',
    message_rewrite_enabled: true, cycle_message_preview: '',
    account_slots: [], account_states: {},
  })
  const [configuredSlots, setConfiguredSlots] = useState([])
  const [subscriptionSlots, setSubscriptionSlots] = useState([])
  const [connected, setConnected] = useState(false)
  const [activeTab, setActiveTab] = useState('logs')
  const [logScope, setLogScope] = useState('account') // account | all
  const [showGroups, setShowGroups] = useState(false)
  const [groups, setGroups] = useState([])
  const [groupsListMeta, setGroupsListMeta] = useState(null)
  const [copied, setCopied] = useState(false)
  const [refreshingJoinedSlot, setRefreshingJoinedSlot] = useState(null)
  const membershipAutoRefreshRef = useRef(false)
  const membershipRefreshInFlightRef = useRef(new Set())
  const [initialLoading, setInitialLoading] = useState(true)
  const [hardRefreshing, setHardRefreshing] = useState(false)
  const [totalListLoading, setTotalListLoading] = useState(false)
  const [bulkActionLoading, setBulkActionLoading] = useState(null) // 'start' | 'stop'
  const [accountActionLoading, setAccountActionLoading] = useState(null) // account1:start
  const [switchingAccount, setSwitchingAccount] = useState(null)
  const [mainView, setMainView] = useState('dashboard') // dashboard | inbox
  const [inboxState, setInboxState] = useState({ slots: {} })
  const [crmState, setCrmState] = useState({
    leads: {},
    stats: {},
    due_reminders: [],
    scheduled_calls: {},
    call_reminders: [],
    past_due_calls: [],
  })
  const [inboxLiveEvent, setInboxLiveEvent] = useState(null)
  const [incomingCall, setIncomingCall] = useState(null)
  useEffect(() => {
    switchingAccountRef.current = switchingAccount
  }, [switchingAccount])
  const [clearingLogs, setClearingLogs] = useState(false)
  const [loadingGroups, setLoadingGroups] = useState(false)
  const [exportingKind, setExportingKind] = useState(null)
  const logsEndRef = useRef(null)  // kept for compatibility but unused
  const wsRef = useRef(null)
  const switchingAccountRef = useRef(null)
  const { confirm } = useConfirm()
  const activeAcctState = state.account_states?.[state.active_account]
  const allAccountLogs = useMemo(() => {
    const states = state.account_states || {}
    return Object.entries(states)
      .flatMap(([slot, acctState]) => (
        (acctState?.logs ?? []).map(entry => ({
          ...entry,
          account_id: entry.account_id || slot,
        }))
      ))
      .sort((a, b) => {
        const at = Date.parse(a.timestamp || '') || 0
        const bt = Date.parse(b.timestamp || '') || 0
        return at - bt
      })
  }, [state.account_states])
  const accountLogs = activeAcctState?.logs ?? []
  const displayLogs = logScope === 'all' ? allAccountLogs : accountLogs
  // Newest log lines at top, older below
  const displayLogsNewestFirst = [...displayLogs].reverse()

  const fetchInbox = React.useCallback(() => {
    fetch(`${API}/inbox?sync=0&t=${Date.now()}`, { cache: 'no-store' })
      .then(r => (r.ok ? r.json() : null))
      .then(data => {
        if (data?.status === 'ok' && data.slots) setInboxState({ slots: data.slots })
      })
      .catch(() => {})
    fetchCrmState()
      .then(crm => setCrmState(crm))
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (mainView !== 'inbox') return undefined
    const intervalMs = connected ? 45000 : 12000
    const id = window.setInterval(() => fetchInbox(), intervalMs)
    return () => clearInterval(id)
  }, [mainView, connected, fetchInbox])

  const handleCrmUpdate = React.useCallback((crm, lead, call) => {
    if (crm) {
      setCrmState({
        leads: crm.leads || {},
        stats: crm.stats || {},
        due_reminders: crm.due_reminders || [],
        scheduled_calls: crm.scheduled_calls || {},
        call_reminders: crm.call_reminders || [],
        past_due_calls: crm.past_due_calls || [],
        block_list: crm.block_list || {},
        blocked_count: crm.blocked_count ?? 0,
      })
    }
    const slot = lead?.account_id || call?.account_id
    const rawUid = lead?.user_id ?? call?.user_id
    if (!slot || rawUid == null) return
    const uid = Number(rawUid)
    const reminderDue = lead && lead.status !== 'spam' && lead.reminder_timestamp
      ? (() => {
          try {
            return new Date(lead.reminder_timestamp).getTime() <= Date.now()
          } catch {
            return false
          }
        })()
      : false
    setInboxState(prev => {
      const block = prev?.slots?.[slot]
      if (!block) return prev
      const convs = [...(block.conversations || [])]
      const idx = convs.findIndex(c => Number(c.user_id) === uid)
      if (idx < 0) return prev
      const patch = { ...convs[idx] }
      if (lead) {
        patch.crm_status = lead.status ?? patch.crm_status
        patch.crm_notes = lead.notes ?? patch.crm_notes
        patch.crm_reminder_timestamp = lead.reminder_timestamp
        patch.crm_reminder_due = reminderDue
        patch.crm_last_contact_time = lead.last_contact_time ?? patch.crm_last_contact_time
        patch.crm_last_reply_at = lead.last_reply_at ?? patch.crm_last_reply_at
        patch.last_reply_time = lead.last_reply_at ?? patch.last_reply_time
        patch.crm_last_user_message_at = lead.last_user_message_at ?? patch.crm_last_user_message_at
        patch.last_user_message_at = lead.last_user_message_at ?? patch.last_user_message_at
        patch.crm_reply_handled_at = lead.reply_handled_at ?? patch.crm_reply_handled_at
        patch.reply_handled_at = lead.reply_handled_at ?? patch.reply_handled_at

        const userIso = lead.last_user_message_at ?? patch.crm_last_user_message_at
        const replyIso = lead.last_reply_at ?? patch.crm_last_reply_at
        const handledIso = lead.reply_handled_at ?? patch.crm_reply_handled_at
        const userAt = userIso ? Date.parse(userIso) : NaN
        const replyAt = replyIso ? Date.parse(replyIso) : NaN
        const handledAt = handledIso ? Date.parse(handledIso) : NaN
        const eff = Math.max(
          Number.isFinite(replyAt) ? replyAt : 0,
          Number.isFinite(handledAt) ? handledAt : 0,
        )
        let alertLevel = null
        if (Number.isFinite(userAt) && eff >= userAt) {
          alertLevel = null
        } else if (Number.isFinite(userAt)) {
          const elapsed = Date.now() - userAt
          if (elapsed >= 20 * 60 * 1000) alertLevel = 'aggressive'
          else if (elapsed >= 10 * 60 * 1000) alertLevel = 'buzzer'
          else if (elapsed >= 5 * 60 * 1000) alertLevel = 'soft'
        }
        patch.crm_reply_alert_level = alertLevel
        patch.crm_reply_delayed = alertLevel === 'buzzer' || alertLevel === 'aggressive'
      }
      if (call) {
        if (call.status === 'scheduled') {
          patch.crm_scheduled_call = call
        }
        if (call.call_attempted) {
          patch.crm_last_live_call = call
        }
      }
      if (lead?.status === 'spam') {
        patch.crm_blocked = true
        patch.crm_status = 'spam'
      } else if (lead?.status === 'new') {
        patch.crm_blocked = false
        patch.crm_status = 'new'
      }
      convs[idx] = patch
      return {
        ...prev,
        slots: {
          ...prev.slots,
          [slot]: { ...block, conversations: convs },
        },
      }
    })
  }, [])

  useEffect(() => {
    const unlock = () => unlockNotificationSound()
    document.addEventListener('click', unlock, { capture: true, passive: true })
    document.addEventListener('keydown', unlock, { capture: true, passive: true })
    const onVisible = () => {
      if (document.visibilityState === 'visible') unlockNotificationSound()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      document.removeEventListener('click', unlock, { capture: true })
      document.removeEventListener('keydown', unlock, { capture: true })
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [])

  useEffect(() => {
    const bootTimeout = setTimeout(() => setInitialLoading(false), 8000)
    Promise.all([
      fetch(`${API}/accounts?t=${Date.now()}`, { cache: 'no-store' })
        .then(r => (r.ok ? r.json() : null))
        .then(data => {
          if (data?.account_slots?.length) setConfiguredSlots(data.account_slots)
          if (Array.isArray(data?.subscription_slots)) setSubscriptionSlots(data.subscription_slots)
        }),
      fetch(`${API}/state?t=${Date.now()}`, { cache: 'no-store' })
        .then(r => (r.ok ? r.json() : null))
        .then(data => {
          if (data) {
            if (Array.isArray(data.subscription_slots)) setSubscriptionSlots(data.subscription_slots)
            setState(prev => ({
              ...prev,
              ...data,
              active_account: data.active_account || data.account_slots?.[0] || prev.active_account,
            }))
            setInitialLoading(false)
          }
        }),
    ]).catch(() => {}).finally(() => setInitialLoading(false))
    connect()
    return () => {
      clearTimeout(bootTimeout)
      wsRef.current?.close()
    }
  }, [])

  useEffect(() => {
    if (connected) setInitialLoading(false)
  }, [connected])

  const logsContainerRef = useRef(null)
  const userScrolledDown = useRef(false)

  function handleLogsScroll(e) {
    const el = e.target
    userScrolledDown.current = el.scrollTop > 40
  }

  function connect() {
    const ws = new WebSocket(WS)
    wsRef.current = ws
    ws.onopen = () => {
      setConnected(true)
      fetch(`${API}/state?t=${Date.now()}`, { cache: 'no-store' })
        .then(r => (r.ok ? r.json() : null))
        .then(data => { if (data) setState(prev => ({ ...prev, ...data })) })
        .catch(() => {})
      fetchInbox()
    }
    ws.onclose = () => { setConnected(false); setTimeout(connect, 3000) }
    ws.onerror = () => ws.close()
    ws.onmessage = (e) => {
      let data
      try {
        data = JSON.parse(e.data)
      } catch {
        return
      }
      if (data.type === 'membership' && data.slot) {
        setState(prev => {
          const prevInfo = prev.account_info?.[data.slot] || {}
          return {
            ...prev,
            account_info: {
              ...prev.account_info,
              [data.slot]: {
                ...prevInfo,
                joined_groups: data.joined_groups,
                joined_channels: data.joined_channels,
                joined_total: data.joined_total,
                joined_updated_at: data.joined_updated_at,
                membership_stale: data.membership_stale ?? false,
                membership_age_seconds: data.membership_age_seconds ?? null,
              },
            },
          }
        })
      }
      if (data.type === 'state') {
        const { type, status, ...rest } = data
        if (Array.isArray(rest.subscription_slots)) {
          setSubscriptionSlots(rest.subscription_slots)
        }
        setState(prev => {
          if (switchingAccountRef.current) {
            return {
              ...prev,
              ...rest,
              active_account: prev.active_account,
              logs: prev.logs,
              running: prev.running,
              current_group: prev.current_group,
              success: prev.success,
              failed: prev.failed,
              success_list: prev.success_list,
              failed_list: prev.failed_list,
              active_groups: prev.active_groups,
              notification: prev.notification,
              cycle: prev.cycle,
              cycle_message_preview: prev.cycle_message_preview,
              heavy_rate_limit: prev.heavy_rate_limit,
              next_cycle_in: prev.next_cycle_in,
              custom_message: prev.custom_message,
            }
          }
          return { ...prev, ...rest }
        })
      }
      if (data.type === 'daily_stats' && data.daily_stats) {
        setState(prev => ({ ...prev, daily_stats: data.daily_stats }))
      }
      if (data.type === 'event' && data.event === 'STATS_RESET' && data.data?.daily_stats) {
        setState(prev => ({ ...prev, daily_stats: data.data.daily_stats }))
      }
      if (data.type === 'inbox') {
        setInboxState(prev => mergeInboxWs(prev, data))
        if (
          data.event === 'new_message'
          && data.message
          && data.message.direction === 'in'
        ) {
          playNewMessageSound({
            slot: data.slot,
            messageId: data.message.id,
          })
        }
        if (data.message || data.event === 'message_read' || data.event === 'message_status') {
          setInboxLiveEvent({
            slot: data.slot,
            event: data.event,
            message: data.message,
            conversation: data.conversation,
            ts: Date.now(),
          })
        }
      }
      if (data.type === 'crm') {
        if (data.crm) {
          setCrmState({
            leads: data.crm.leads || {},
            stats: data.crm.stats || {},
            due_reminders: data.crm.due_reminders || [],
            scheduled_calls: data.crm.scheduled_calls || {},
            call_reminders: data.crm.call_reminders || [],
            past_due_calls: data.crm.past_due_calls || [],
          })
        }
        if (data.conversation && data.slot) {
          setInboxState(prev => mergeInboxWs(prev, {
            slot: data.slot,
            event: data.event || 'lead_updated',
            conversation: data.conversation,
          }))
        }
      }
      if (data.type === 'incoming_call') {
        if (data.event === 'ringing' && data.call && data.slot) {
          unlockNotificationSound()
          startIncomingCallRing()
          const row = { ...data.call, slot: data.slot }
          setIncomingCall(row)
          if (typeof Notification !== 'undefined') {
            if (Notification.permission === 'default') {
              Notification.requestPermission().catch(() => {})
            }
            if (Notification.permission === 'granted') {
              try {
                new Notification(`Incoming call — ${row.name || 'Contact'}`, {
                  body: `Answer in Telegram · ${accountLabel(data.slot)}`,
                  tag: `call-${data.slot}-${row.call_id}`,
                  requireInteraction: true,
                })
              } catch {
                /* ignore */
              }
            }
          }
        } else if (data.event === 'ended') {
          stopIncomingCallRing()
          setIncomingCall(prev => {
            if (!prev) return null
            if (data.call?.call_id != null && prev.call_id !== data.call.call_id) return prev
            return null
          })
        }
      }
    }
  }

  async function refreshAccounts() {
    try {
      const res = await fetch(`${API}/state?t=${Date.now()}`, { cache: 'no-store' })
      if (res.ok) {
        const data = await res.json()
        const { type: _t, ...rest } = data
        setState(prev => ({ ...prev, ...rest }))
        return
      }
    } catch { /* fallback below */ }
    const res = await fetch(`${API}/account/status`)
    const data = await res.json()
    const active = data.active_account
    const msgRes = await fetch(
      `${API}/message${active ? `?slot=${encodeURIComponent(active)}` : ''}`
    )
    const msgData = await msgRes.json()
    setState(prev => ({
      ...prev,
      active_account: active ?? prev.active_account,
      account_info: data.account_info || {},
      account_states: data.account_states || prev.account_states,
      custom_message: msgData.message || prev.custom_message,
    }))
  }

  async function refreshJoinedCounts(slot, { quiet = false } = {}) {
    if (membershipRefreshInFlightRef.current.has(slot)) return
    membershipRefreshInFlightRef.current.add(slot)
    if (!quiet) setRefreshingJoinedSlot(slot)
    try {
      const res = await fetch(`${API}/account/refresh-joined`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ slot }),
      })
      const data = await res.json()
      if (!data.success) {
        if (!quiet) alert(data.error || 'Failed to scan Telegram membership')
        return
      }
      if (!quiet && data.queued && data.message) {
        alert(data.message)
      }
      await refreshAccounts()
      if (!data.queued && data.joined_total != null) {
        return
      }
      if (quiet) return
      // Running account: poll until counts land (WebSocket may also update)
      for (let i = 0; i < 24; i++) {
        await new Promise(r => setTimeout(r, 5000))
        await refreshAccounts()
        const info = (await fetch(`${API}/account/status`).then(r => r.json())).account_info?.[slot]
        if (formatJoinedStats(info) && !isMembershipStale(info)) return
      }
    } catch (e) {
      if (!quiet) alert('Failed to scan: ' + e.message)
    } finally {
      membershipRefreshInFlightRef.current.delete(slot)
      if (!quiet) setRefreshingJoinedSlot(null)
    }
  }

  useEffect(() => {
    if (!connected || membershipAutoRefreshRef.current) return
    membershipAutoRefreshRef.current = true
    const info = state.account_info || {}
    Object.keys(info).forEach(slot => {
      if (isMembershipStale(info[slot])) {
        refreshJoinedCounts(slot, { quiet: true })
      }
    })
  }, [connected])

  useEffect(() => {
    const slot = state.active_account
    if (!slot || !connected) return
    const info = state.account_info?.[slot]
    if (info && isMembershipStale(info)) {
      refreshJoinedCounts(slot, { quiet: true })
    }
  }, [state.active_account, connected])

  async function hardRefresh() {
    setHardRefreshing(true)
    wsRef.current?.close()
    try {
      const res = await fetch(`${API}/state?t=${Date.now()}`, { cache: 'no-store' })
      if (res.ok) {
        const data = await res.json()
        setState(prev => ({ ...prev, ...data }))
      }
    } catch {
      /* full reload below */
    }
    const url = new URL(window.location.href)
    url.searchParams.set('hard', Date.now().toString())
    window.location.replace(url.pathname + url.search + url.hash)
  }

  function mirrorActiveAccountFields(acctState) {
    if (!acctState) return { logs: [] }
    return {
      logs: acctState.logs ?? [],
      success: acctState.success ?? 0,
      failed: acctState.failed ?? 0,
      success_list: acctState.success_list ?? [],
      failed_list: acctState.failed_list ?? [],
      current_group: acctState.current_group ?? '',
      running: !!acctState.running,
      cycle: acctState.cycle ?? 0,
      active_groups: acctState.active_groups ?? 0,
      notification: acctState.notification ?? '',
      heavy_rate_limit: !!acctState.heavy_rate_limit,
      next_cycle_in: acctState.next_cycle_in ?? 0,
      status: acctState.status ?? 'stopped',
      cycle_message_preview: acctState.cycle_message_preview ?? '',
    }
  }

  async function switchAccount(slot) {
    if (!slot || slot === state.active_account) return
    setSwitchingAccount(slot)
    setState(prev => ({
      ...prev,
      active_account: slot,
      custom_message: prev.account_messages?.[slot] ?? prev.custom_message,
      ...mirrorActiveAccountFields(prev.account_states?.[slot]),
    }))
    const controller = new AbortController()
    const timeoutId = window.setTimeout(() => controller.abort(), 8000)
    try {
      await fetch(`${API}/account/switch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ slot }),
        signal: controller.signal,
      })
      const msgRes = await fetch(`${API}/message?slot=${encodeURIComponent(slot)}`, {
        signal: controller.signal,
      })
      if (msgRes.ok) {
        const msgData = await msgRes.json()
        setState(prev => ({ ...prev, custom_message: msgData.message || prev.custom_message }))
      }
    } catch {
      /* WebSocket will sync state */
    } finally {
      window.clearTimeout(timeoutId)
      setSwitchingAccount(null)
    }
  }

  const accountSlots = getAccountSlots(state, configuredSlots)
  const loggedInSlots = useMemo(
    () => getLoggedInSlots(accountSlots, state.account_info),
    [accountSlots, state.account_info],
  )
  const fleet = useMemo(
    () => aggregateFleetStats(state, loggedInSlots),
    [state, loggedInSlots],
  )
  const sentWindowLabel = state.daily_stats?.window === 'since_reset' ? 'Since reset' : 'Last 24h'
  const inboxUnreadTotal = useMemo(
    () => computeInboxUnreadTotal(inboxState),
    [inboxState],
  )
  const inboxUnreadBadge = formatUnreadBadgeCount(inboxUnreadTotal)

  useEffect(() => {
    syncInboxAlertMusic(inboxUnreadTotal)
    return () => stopInboxAlertMusicOnUnmount()
  }, [inboxUnreadTotal])

  useEffect(() => {
    const resync = () => syncInboxAlertMusic(inboxUnreadTotal)
    window.addEventListener('sound-quiet-hours-change', resync)
    const tick = window.setInterval(resync, 60000)
    return () => {
      window.removeEventListener('sound-quiet-hours-change', resync)
      clearInterval(tick)
    }
  }, [inboxUnreadTotal])
  const loggedIn = loggedInSlots.length > 0
  const idleLoggedInSlots = loggedInSlots.filter(
    s => !state.account_states?.[s]?.running
  )
  const canStartMore = idleLoggedInSlots.length > 0

  async function startForwarding() {
    setBulkActionLoading('start')
    const controller = new AbortController()
    const timeoutId = window.setTimeout(() => controller.abort(), 10000)
    try {
      const res = await fetch(`${API}/start`, { method: 'POST', signal: controller.signal })
      if (res.ok) {
        const data = await res.json().catch(() => null)
        if (data) {
          setState(prev => ({ ...prev, ...data }))
        }
      }
      window.setTimeout(refreshAccounts, 1500)
    } finally {
      window.clearTimeout(timeoutId)
      setBulkActionLoading(null)
    }
  }
  async function startTest() {
    await fetch(`${API}/start-test`, { method: 'POST' })
  }
  async function stopForwarding() {
    setBulkActionLoading('stop')
    try {
      const res = await fetch(`${API}/stop`, { method: 'POST' })
      if (res.ok) {
        const data = await res.json()
        const { status: _st, ...rest } = data
        setState(prev => ({ ...prev, ...rest }))
      } else {
        setState(prev => ({
          ...prev,
          running: false,
          current_group: '',
          account_states: Object.fromEntries(
            getAccountSlots(prev, configuredSlots).map(slot => [
              slot,
              { ...prev.account_states?.[slot], running: false, current_group: '' },
            ])
          ),
        }))
      }
    } finally {
      setBulkActionLoading(null)
    }
  }
  async function startAccount(slot, oneShot = false) {
    setAccountActionLoading(`${slot}:start`)
    try {
      const url = oneShot
        ? `${API}/account/${slot}/start?one_shot=true`
        : `${API}/account/${slot}/start`
      await fetch(url, { method: 'POST' })
    } finally {
      setAccountActionLoading(null)
    }
  }
  async function stopAccount(slot) {
    setAccountActionLoading(`${slot}:stop`)
    try {
      const res = await fetch(`${API}/account/${slot}/stop`, { method: 'POST' })
      if (res.ok) {
        const data = await res.json()
        const { status: _st, slot: _slot, ...rest } = data
        setState(prev => ({ ...prev, ...rest }))
      }
    } finally {
      setAccountActionLoading(null)
    }
  }

  async function clearLogs() {
    const slot = state.active_account || 'account1'
    setClearingLogs(true)
    try {
      const res = await fetch(`${API}/account/${slot}/clear-logs`, { method: 'POST' })
      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.message || data.detail || `HTTP ${res.status}`)
      }
      const { status: _st, slot: _sl, ...uiState } = data
      setState(prev => ({ ...prev, ...uiState }))
      userScrolledDown.current = false
    } catch (e) {
      alert('Failed to clear logs: ' + e.message)
    } finally {
      setClearingLogs(false)
    }
  }

  async function openGroups() {
    setShowGroups(true)
    const slot = state.active_account || 'account1'
    setLoadingGroups(true)
    try {
      const reqs = [fetch(`${API}/groups/lists?slot=${encodeURIComponent(slot)}`)]
      if (!groups.length) reqs.unshift(fetch(`${API}/groups`))
      const results = await Promise.all(reqs)
      let i = 0
      if (!groups.length) {
        const data = await results[i++].json()
        setGroups(data.groups || [])
      }
      if (results[i]?.ok) setGroupsListMeta(await results[i].json())
    } catch (e) {
      alert('Failed to load groups: ' + e.message)
      setShowGroups(false)
    } finally {
      setLoadingGroups(false)
    }
  }

  function downloadTextFile(filename, text) {
    const blob = new Blob([text], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  async function exportGroupLists(kind) {
    const slot = state.active_account || 'account1'
    setExportingKind(kind)
    try {
      const res = await fetch(`${API}/groups/lists?slot=${slot}`)
      const ct = res.headers.get('content-type') || ''
      if (!res.ok || !ct.includes('application/json')) {
        throw new Error(
          res.ok
            ? 'Backend returned HTML instead of JSON — restart the server (python scripts/dev.py)'
            : `HTTP ${res.status} — restart backend if you just updated code`
        )
      }
      const data = await res.json()
      const sep = '='.repeat(48)
      if (kind === 'dead') {
        const lines = [
          `Dead groups — ${slot}`,
          `Total master: ${data.total_master} | Dead: ${data.dead_count}`,
          sep,
          '',
          `INVALID (${data.invalid.length}) — username not found`,
          ...data.invalid.map((g, i) => `${i + 1}. ${g}`),
          '',
          `BLOCKED (${data.blocked.length}) — cannot post / admin channel`,
          ...data.blocked.map((g, i) => `${i + 1}. ${g}`),
        ]
        downloadTextFile(`dead_groups_${slot}.txt`, lines.join('\n'))
      } else if (kind === 'good') {
        const lines = [
          `Active groups — ${slot}`,
          `Still in rotation (master minus dead): ${data.active_count}`,
          sep,
          '',
          `ACTIVE (${data.active.length})`,
          ...data.active.map((g, i) => `${i + 1}. ${g}`),
        ]
        downloadTextFile(`active_groups_${slot}.txt`, lines.join('\n'))
      } else if (kind === 'success') {
        const lines = [
          `Success this cycle — ${slot} (${data.cycle_success_count})`,
          sep,
          ...data.cycle_success.map((g, i) => `${i + 1}. ${g}`),
        ]
        downloadTextFile(`success_cycle_${slot}.txt`, lines.join('\n'))
      }
    } catch (e) {
      alert('Failed to export: ' + e.message)
    } finally {
      setExportingKind(null)
    }
  }

  function downloadGroups() {
    const text = groups.map((g, i) => `${i + 1}. ${g}`).join('\n')
    downloadTextFile('groups_list.txt', `Telegram Groups List (${groups.length} total)\n${'='.repeat(40)}\n\n${text}`)
  }

  function downloadCsvFile(filename, csvText) {
    const blob = new Blob(['\ufeff' + csvText], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  function csvEscape(value) {
    if (value === null || value === undefined) return ''
    const s = String(value)
    if (/[",\n\r]/.test(s)) return '"' + s.replace(/"/g, '""') + '"'
    return s
  }

  async function buildTotalList() {
    if (totalListLoading) return
    setTotalListLoading(true)
    try {
      const res = await fetch(`${API}/groups/total-list`)
      const ct = res.headers.get('content-type') || ''
      if (!res.ok || !ct.includes('application/json')) {
        throw new Error(res.ok ? 'Backend returned non-JSON' : `HTTP ${res.status}`)
      }
      const data = await res.json()
      const items = Array.isArray(data.items) ? data.items : []
      const usernames = [...new Set(
        items
          .map(it => (it.username || '').trim().replace(/^@/, ''))
          .filter(Boolean),
      )].sort((a, b) => a.localeCompare(b, undefined, { sensitivity: 'base' }))
      if (usernames.length === 0) {
        const msg =
          'No joined groups with usernames found. Some accounts may not have a string session — fallback uses the worker session ' +
          'and can fail if the worker is mid-cycle. Try again in a moment.'
        alert(msg)
        return
      }
      const csv = ['username', ...usernames.map(csvEscape)].join('\n')
      const ts = new Date()
      const stamp = `${ts.getFullYear()}${String(ts.getMonth() + 1).padStart(2, '0')}${String(ts.getDate()).padStart(2, '0')}_${String(ts.getHours()).padStart(2, '0')}${String(ts.getMinutes()).padStart(2, '0')}`
      downloadCsvFile(`total_joined_list_${stamp}.csv`, csv)

      const errs = Object.entries(data.per_account || {})
        .filter(([, v]) => v?.error)
        .map(([slot, v]) => `${slot}: ${v.error}`)
      if (errs.length) {
        alert(`Saved ${usernames.length} usernames.\n\nNote — these accounts could not scan:\n${errs.join('\n')}`)
      }
    } catch (e) {
      alert('Total List failed: ' + (e?.message || e))
    } finally {
      setTotalListLoading(false)
    }
  }

  const [countdown, setCountdown] = useState(0)
  const [globalCountdown, setGlobalCountdown] = useState(0)
  const [cycleElapsed, setCycleElapsed] = useState(0)
  const cycleStartRef = useRef(null)

  // Sync countdown from server
  useEffect(() => {
    const serverVal = activeAcctState?.next_cycle_in ?? 0
    if (serverVal > 0) setCountdown(serverVal)
  }, [activeAcctState?.next_cycle_in])

  useEffect(() => {
    const serverVal = fleet.minCountdown ?? 0
    if (serverVal > 0) setGlobalCountdown(serverVal)
  }, [fleet.minCountdown])

  // Count down every second
  useEffect(() => {
    if (countdown <= 0) return
    const timer = setInterval(() => {
      setCountdown(prev => Math.max(0, prev - 1))
    }, 1000)
    return () => clearInterval(timer)
  }, [countdown > 0])

  useEffect(() => {
    if (globalCountdown <= 0) return
    const timer = setInterval(() => {
      setGlobalCountdown(prev => Math.max(0, prev - 1))
    }, 1000)
    return () => clearInterval(timer)
  }, [globalCountdown > 0])

  // Track cycle elapsed time for active account
  useEffect(() => {
    const running = !!activeAcctState?.running
    if (running) {
      if (!cycleStartRef.current) cycleStartRef.current = Date.now()
      const timer = setInterval(() => {
        setCycleElapsed(Math.floor((Date.now() - cycleStartRef.current) / 1000))
      }, 1000)
      return () => clearInterval(timer)
    }
    cycleStartRef.current = null
    setCycleElapsed(0)
  }, [activeAcctState?.running, state.active_account])
  const displaySuccess = activeAcctState?.success ?? state.success
  const displayFailed = activeAcctState?.failed ?? state.failed
  const displayCurrentGroup = activeAcctState?.current_group || state.current_group
  const displayActiveGroups = activeAcctState?.active_groups ?? state.active_groups
  const displaySent24h = activeAcctState?.messages_sent_24h ?? 0
  const displaySkippedPosted = activeAcctState?.skipped_already_posted ?? 0
  const displaySkippedCooldown = activeAcctState?.skipped_cooldown ?? 0
  const displaySkippedOther = activeAcctState?.skipped_other ?? 0
  const displaySuccessList = activeAcctState?.success_list ?? state.success_list
  const displayFailedList = activeAcctState?.failed_list ?? state.failed_list
  const displaySuccessNewestFirst = [...displaySuccessList].reverse()
  const displayFailedNewestFirst = [...displayFailedList].reverse()

  useEffect(() => {
    const el = logsContainerRef.current
    if (!el) return
    // Keep view pinned to top (newest) unless user scrolled down to read older lines
    if (!userScrolledDown.current) {
      el.scrollTop = 0
    }
  }, [displayLogs, displaySuccessList, displayFailedList, activeTab])

  const total = displaySuccess + displayFailed
  const successRate = total > 0 ? ((displaySuccess / total) * 100).toFixed(1) : '0.0'
  const processed = displaySuccess + displayFailed
  const progressMax = state.total || 1
  // skipped = groups where our msg was already last (didn't need sending)
  const skipped = progressMax - (displayActiveGroups || 0)
  // Only show progress if a cycle has actually run
  const hasCycleRun = (activeAcctState?.cycle ?? 0) > 0
  const progressValue = hasCycleRun ? Math.min(progressMax, skipped + processed) : 0

  const showBootOverlay = initialLoading && !connected

  return (
    <div className={`app-shell${showBootOverlay ? ' app-shell--booting' : ''}`}>
      {showBootOverlay && (
        <div className="app-boot-overlay" role="status" aria-live="polite">
          <Spinner size={32} />
          <span className="overlay-loader-label">Connecting to server…</span>
        </div>
      )}

      <header className="app-header">
        <div className="app-header-left">
          <div className="app-header-title">
            <h1>Telegram Forwarder</h1>
            <p className="app-header-sub">
              Multi-account automation · live status
              {state.active_account && state.account_info?.[state.active_account] && (
                <span className="app-header-active-user">
                  · Viewing {state.account_info[state.active_account].name}
                </span>
              )}
            </p>
          </div>
        </div>

        <div className="app-header-center">
          <SoundQuietHoursToggle />
        </div>

        <div className="app-header-right">
          <nav className="app-view-nav" aria-label="Main view">
            <button
              type="button"
              className={`app-view-nav-btn${mainView === 'dashboard' ? ' app-view-nav-btn--active' : ''}`}
              onClick={() => {
                unlockNotificationSound()
                setMainView('dashboard')
              }}
            >
              Dashboard
            </button>
            <button
              type="button"
              className={`app-view-nav-btn${mainView === 'inbox' ? ' app-view-nav-btn--active' : ''}${inboxUnreadTotal > 0 ? ' app-view-nav-btn--has-unread' : ''}`}
              onClick={() => { setMainView('inbox'); fetchInbox() }}
              aria-label={
                inboxUnreadTotal > 0
                  ? `Inbox, ${inboxUnreadTotal} unread message${inboxUnreadTotal === 1 ? '' : 's'}`
                  : 'Inbox'
              }
            >
              Inbox
              {inboxUnreadTotal > 0 && (
                <span className="app-view-nav-badge" aria-hidden>
                  {inboxUnreadBadge}
                </span>
              )}
            </button>
          </nav>
          <GlobalActions
            connected={connected}
            canStartMore={canStartMore}
            anyRunning={loggedInSlots.some(s => state.account_states?.[s]?.running)}
            bulkActionLoading={bulkActionLoading}
            hardRefreshing={hardRefreshing}
            totalListLoading={totalListLoading}
            onStartAll={startForwarding}
            onStopAll={stopForwarding}
            onHardRefresh={hardRefresh}
            onTotalList={buildTotalList}
          />
        </div>
      </header>

      {mainView === 'inbox' ? (
        <InboxPanel
          inboxState={inboxState}
          inboxLiveEvent={inboxLiveEvent}
          accountSlots={accountSlots}
          crmState={crmState}
          onInboxPatch={fetchInbox}
          onCrmUpdate={handleCrmUpdate}
        />
      ) : (
      <ResizableDashboardLayout
        left={(
        <DashboardColumn
          id="left"
          title="Column 1 · Setup"
          subtitle="Accounts, message, groups"
        >
          <AccountPanel
            state={state}
            configuredSlots={configuredSlots}
            subscriptionSlots={subscriptionSlots.length ? subscriptionSlots : (state.subscription_slots || [])}
            onAccountChange={refreshAccounts}
            onStartAccount={startAccount}
            onStopAccount={stopAccount}
            onSwitchAccount={switchAccount}
            onRefreshJoined={refreshJoinedCounts}
            refreshingJoinedSlot={refreshingJoinedSlot}
            accountActionLoading={accountActionLoading}
            switchingAccount={switchingAccount}
          />
          <MessageEditor
            slot={state.active_account}
            customMessage={state.custom_message}
            rewriteEnabled={state.message_rewrite_enabled}
            cyclePreview={state.cycle_message_preview}
            onSaved={refreshAccounts}
          />
          <GroupsUpload
            currentTotal={state.total || 0}
            onUpdated={refreshAccounts}
            listSummary={groupsListMeta ? {
              active: groupsListMeta.active_count,
              dead: groupsListMeta.dead_count,
            } : null}
          />
        </DashboardColumn>
        )}
        center={(
        <DashboardColumn
          id="center"
          title="Progress"
          subtitle={state.active_account ? accountLabel(state.active_account) : 'Fleet monitor'}
          flush
        >
          <ProgressHubPanel
            fleet={fleet}
            globalCountdown={globalCountdown}
            sentWindowLabel={sentWindowLabel}
            accountInfo={state.account_info}
            subscriptionSlots={subscriptionSlots.length ? subscriptionSlots : (state.subscription_slots || [])}
            dailyStats={state.daily_stats}
            accountSlots={accountSlots}
            onConfirmReset={({ scope, accountLabel: acctLabel }) => confirm({
              title: scope === 'account' ? `Reset stats for ${acctLabel}?` : 'Reset 24 Hours',
              message:
                scope === 'account'
                  ? `Reset 24-hour stats for ${acctLabel}? Only counters are cleared — chat history, messages, and sessions are preserved.`
                  : 'Are you sure you want to reset 24-hour stats? Only counters are cleared — chat history, messages, and sessions are preserved.',
              confirmLabel: 'Reset stats',
              cancelLabel: 'Cancel',
              variant: 'warn',
            })}
            onDailyStatsUpdate={(stats, full) => {
              if (full) {
                const { type, status, daily_stats: _ds, ...rest } = full
                setState(prev => ({ ...prev, ...rest, daily_stats: stats || full.daily_stats }))
              } else {
                setState(prev => ({ ...prev, daily_stats: stats }))
              }
            }}
            activeAccount={state.active_account}
            activeAcctState={activeAcctState}
            accountStates={state.account_states}
            onSelectAccount={switchAccount}
            switchingAccount={switchingAccount}
            accountProgress={{
              displaySuccess,
              displayFailed,
              successRate,
              processed,
              displayActiveGroups,
              displaySkippedPosted,
              displaySkippedCooldown,
              displaySkippedOther,
              displaySent24h,
            }}
            cycle={{
              displayCurrentGroup,
              countdown,
              cycleElapsed,
              progressValue,
              progressMax,
              hasCycleRun,
            }}
            tools={{
              openGroups,
              exportGroupLists,
              loadingGroups,
              exportingKind,
              onResetStats: async () => {
                const ok = await confirm({
                  title: 'Reset all cycle stats?',
                  message: 'Clears success/fail counts and logs for every account in the UI.',
                  confirmLabel: 'Reset',
                  variant: 'warn',
                })
                if (!ok) return
                setState(prev => ({
                  ...prev,
                  success: 0, failed: 0, logs: [],
                  success_list: [], failed_list: [],
                  current_group: '', active_groups: 0,
                  account_states: Object.fromEntries(
                    getAccountSlots(prev, configuredSlots).map(slot => [
                      slot,
                      {
                        ...prev.account_states?.[slot],
                        success: 0,
                        failed: 0,
                        skipped_already_posted: 0,
                        skipped_cooldown: 0,
                        skipped_other: 0,
                        logs: [],
                        success_list: [],
                        failed_list: [],
                        current_group: '',
                      },
                    ])
                  ),
                }))
              },
            }}
          />
        </DashboardColumn>
        )}
        right={(
        <DashboardColumn
          id="right"
          title="Live activity"
          subtitle={logScope === 'all' ? 'All account logs' : (state.active_account ? accountLabel(state.active_account) : 'Select an account')}
          flush
        >
          <LogPanel
            activeTab={activeTab}
            activeAccount={state.active_account}
            accountSlots={state.account_slots}
            logScope={logScope}
            onLogScopeChange={setLogScope}
            displayLogs={displayLogs}
            displaySuccessList={displaySuccessList}
            displayFailedList={displayFailedList}
            logsContainerRef={logsContainerRef}
            onScroll={handleLogsScroll}
            toolbarActions={(
              <LogToolbarActions
                activeTab={activeTab}
                displayLogs={displayLogs}
                displayLogsNewestFirst={displayLogsNewestFirst}
                displaySuccessNewestFirst={displaySuccessNewestFirst}
                displayFailedNewestFirst={displayFailedNewestFirst}
                clearingLogs={clearingLogs}
                copied={copied}
                clearDisabled={logScope === 'all'}
                clearTitle={
                  logScope === 'all'
                    ? 'Switch to Account logs to clear the selected account'
                    : 'Clear logs for selected account'
                }
                onClear={clearLogs}
                onCopy={() => {
                  let text = ''
                  if (activeTab === 'logs') {
                    text = displayLogsNewestFirst.map(e => `${formatLogTime(e.time)}  ${e.msg}`).join('\n')
                  } else if (activeTab === 'success') {
                    text = displaySuccessNewestFirst.join('\n')
                  } else {
                    text = displayFailedNewestFirst.map(e => `${e.group} — ${e.reason}`).join('\n')
                  }
                  navigator.clipboard.writeText(text).then(() => {
                    setCopied(true)
                    setTimeout(() => setCopied(false), 2000)
                  })
                }}
              />
            )}
            activeTabControl={(
              <LogsToolbarTabs
                activeTab={activeTab}
                setActiveTab={setActiveTab}
                logCount={displayLogs.length}
                okCount={displaySuccessList.length}
                failCount={displayFailedList.length}
              />
            )}
          />
        </DashboardColumn>
        )}
      />
      )}

      <GroupsModal
        open={showGroups}
        onClose={() => setShowGroups(false)}
        groups={groups}
        loading={loadingGroups}
        onDownload={downloadGroups}
        slotLists={groupsListMeta}
      />

      <IncomingCallModal
        call={incomingCall}
        onDismiss={() => {
          stopIncomingCallRing()
          setIncomingCall(null)
        }}
      />

    </div>
  )
}
