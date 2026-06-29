import React, { useState, useEffect, useRef, useMemo } from 'react'
import { ResizableDashboardLayout } from './ResizableDashboard.jsx'
import { ButtonContent, OverlayLoader, Spinner } from './Loader.jsx'
import { API, WS, BUILD_STAMP } from './config.js'
import { DashboardColumn } from './components/DashboardColumn.jsx'
import { ResponsiveOptions } from './components/ui/ResponsiveOptions.jsx'
import { AccountPanel } from './components/AccountPanel.jsx'
import { ShutdownListPanel } from './components/ShutdownListPanel.jsx'
import { GroupsUpload } from './components/GroupsUpload.jsx'
import { ModesSetupPanel } from './components/ModesSetupPanel.jsx'
import { SetupAccountPicker } from './components/SetupAccountPicker.jsx'
import { FleetDefaultsPanel } from './components/FleetDefaultsPanel.jsx'
import { SetupMainPanel } from './components/SetupMainPanel.jsx'
import {
  loadWorkspaceMode,
  saveWorkspaceMode,
  WORKSPACE_CAMPAIGN,
  WORKSPACE_FLEET,
  WORKSPACE_FORWARDING,
  WORKSPACE_MODE_OPTIONS,
} from './utils/workspaceMode.js'
import {
  fleetAnyProcessRunning,
  fleetWorkspaceAnyRunning,
  fleetWorkspaceCanStartMore,
  resolveWorkspaceSync,
} from './utils/workspaceDashboard.js'
import { SABHI_ACCOUNTS, SABHI_SETUP } from './utils/sabAccountsUi.js'
import { GroupsModal } from './components/GroupsModal.jsx'
import { GlobalActions } from './components/GlobalActions.jsx'
import { AppViewNav } from './components/AppViewNav.jsx'
import { ProgressHubPanel } from './components/ProgressHubPanel.jsx'
import { aggregateFleetStats, computeSuccessRatePct } from './utils/globalStats.js'
import {
  LogPanel,
  LogsToolbarTabs,
  LogToolbarActions,
} from './components/LogPanel.jsx'
import {
  accountLabel,
  telegramDisplayName,
  formatJoinedStats,
  formatLogTime,
  getAccountSlots,
  getLoggedInSlots,
  isAccountLoggedIn,
  isMembershipStale,
  filterSlotsExcludingShutdown,
  sortAccountsForDisplay,
  isSlotOnShutdownList,
  isCampaignEnabled,
  isForwardingEnabled,
  accountPrimaryMode,
  featureRuntime,
  setupViewForAccountsFilter,
} from './utils/accountUi.js'
import { useConfirm } from './context/ConfirmContext.jsx'
import { statsResetConfirmOptions } from './utils/statsResetConfirm.js'
import { useAuth } from './context/AuthContext.jsx'
import {
  clearOpenChatUrlParams,
  parseOpenChatFromUrl,
  subscribePushOpenChat,
  syncWebPushSubscription,
} from './utils/webPush.js'
import { InboxPanel } from './components/InboxPanel.jsx'
import { CandidatesPanel } from './components/CandidatesPanel.jsx'
import { HandlerKitPanel } from './components/HandlerKitPanel.jsx'
import { DataRoomPanel } from './components/DataRoomPanel.jsx'
import { AdminPanel } from './components/AdminPanel.jsx'
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
import { syncTabUnreadBadge, resetTabUnreadBadge } from './utils/tabUnreadBadge.js'
import { fetchCrmState } from './utils/crm.js'
import { useCompactLayout } from './utils/useCompactLayout.js'
import { useMobileShell } from './utils/useMobileShell.js'
import { MobileApp } from './mobile/MobileApp.jsx'
import { DesktopApp } from './desktop/DesktopApp.jsx'
import { PendingWorksProvider } from './dailyOps/PendingWorksProvider.jsx'


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
  const conversationPatchEvents = new Set([
    'new_message',
    'reply_sent',
    'outgoing_message',
    'message_edited',  // last_message preview / edited flag may have changed
    'message_deleted',
  ])
  if (conversationPatchEvents.has(data.event) && data.conversation) {
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
  if (data.event === 'conversation_deleted' && data.conversation?.user_id != null) {
    const uid = Number(data.conversation.user_id)
    const convs = (next.slots[slot].conversations || []).filter(
      (c) => Number(c.user_id) !== uid,
    )
    next.slots[slot] = { ...next.slots[slot], conversations: convs }
  }
  if (
    (data.event === 'lead_updated' || data.event === 'lead_blocked')
    && data.conversation?.user_id != null
  ) {
    const uid = Number(data.conversation.user_id)
    const conv = data.conversation
    let convs = [...(next.slots[slot].conversations || [])]
    if (conv.crm_blocked || conv.crm_status === 'spam') {
      convs = convs.filter((c) => Number(c.user_id) !== uid)
    } else {
      convs = mergeInboxConversationList(convs, conv)
    }
    next.slots[slot] = { ...next.slots[slot], conversations: convs }
  }
  return next
}


export default function App() {
  const {
    enabled: authEnabled,
    authenticated: authAuthenticated,
    username: authUsername,
    role: authRole,
    reference: authReference,
    logout: authLogout,
  } = useAuth()
  const [openChatTarget, setOpenChatTarget] = useState(() => parseOpenChatFromUrl())
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
  const [logScope, setLogScope] = useState('all') // account | all — default to all accounts so the operator sees the full fleet on open
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
  const [overviewScope, setOverviewScope] = useState('fleet')
  const [workspaceMode, setWorkspaceMode] = useState(loadWorkspaceMode)
  const workspaceBootstrapDoneRef = useRef(false)
  const [mainView, setMainView] = useState('dashboard') // dashboard | inbox | candidates | handler-kit | ...

  useEffect(() => {
    // Handlers have a restricted Data Room (Opportunities only), so do not
    // redirect them away after they deliberately select it from navigation.
    if (authRole === 'handler' && (mainView === 'dashboard' || mainView === 'inbox' || mainView === 'admin' || mainView === 'logs')) {
      setMainView('handler-kit')
    }
  }, [authRole, mainView])

  const [inboxState, setInboxState] = useState({ slots: {} })
  const [crmState, setCrmState] = useState({
    leads: {},
    stats: {},
    due_reminders: [],
    scheduled_calls: {},
    call_reminders: [],
    past_due_calls: [],
  })
  // Queue-based live events so rapid back-to-back WS messages aren't dropped
  // when React batches state updates. InboxPanel drains the queue on each tick.
  const inboxLiveQueueRef = useRef([])
  const [inboxLiveTick, setInboxLiveTick] = useState(0)
  const [incomingCall, setIncomingCall] = useState(null)
  useEffect(() => {
    document.documentElement.dataset.build = BUILD_STAMP
    const url = new URL(window.location.href)
    let changed = false
    for (const key of ['hard', 'v']) {
      if (url.searchParams.has(key)) {
        url.searchParams.delete(key)
        changed = true
      }
    }
    if (changed) {
      window.history.replaceState(null, '', url.pathname + url.search + url.hash)
    }
  }, [])

  useEffect(() => {
    switchingAccountRef.current = switchingAccount
  }, [switchingAccount])
  const [clearingLogs, setClearingLogs] = useState(false)
  const [loadingGroups, setLoadingGroups] = useState(false)
  const [exportingKind, setExportingKind] = useState(null)
  const logsEndRef = useRef(null)  // kept for compatibility but unused
  const wsRef = useRef(null)
  const wsBackoffRef = useRef(1500)
  const switchingAccountRef = useRef(null)
  const switchAbortRef = useRef(null)
  const { confirm } = useConfirm()
  const activeAcctState = state.account_states?.[state.active_account]
  const allAccountLogs = useMemo(() => {
    const states = state.account_states || {}
    const merged = []
    let seq = 0
    for (const [slot, acctState] of Object.entries(states)) {
      for (const entry of acctState?.logs || []) {
        // Preserve original insertion order via `__seq` so entries WITHOUT a
        // timestamp (or with an unparseable one) don't all collapse to epoch=0
        // at the top of the sort. Stable secondary sort by sequence.
        merged.push({
          ...entry,
          account_id: entry.account_id || slot,
          __seq: seq++,
        })
      }
    }
    merged.sort((a, b) => {
      const at = Date.parse(a.timestamp || '')
      const bt = Date.parse(b.timestamp || '')
      const ai = Number.isFinite(at) ? at : null
      const bi = Number.isFinite(bt) ? bt : null
      if (ai != null && bi != null && ai !== bi) return ai - bi
      if (ai == null && bi != null) return 1   // unstamped → end
      if (ai != null && bi == null) return -1
      return a.__seq - b.__seq                  // stable
    })
    return merged
  }, [state.account_states])
  const accountLogs = activeAcctState?.logs ?? []
  const displayLogs = logScope === 'all' ? allAccountLogs : accountLogs
  // Newest log lines at top, older below. Memoized so we don't reallocate the
  // list on every unrelated render (avoids forcing the LogPanel to diff 500
  // bubbles on each WS tick).
  const displayLogsNewestFirst = useMemo(
    () => [...displayLogs].reverse(),
    [displayLogs],
  )

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
    const fromUrl = parseOpenChatFromUrl()
    if (!fromUrl) return
    setOpenChatTarget(fromUrl)
    setMainView('inbox')
    fetchInbox()
    clearOpenChatUrlParams()
  }, [fetchInbox])

  useEffect(() => {
    if (!authAuthenticated) return undefined
    syncWebPushSubscription().catch(() => {})
    return undefined
  }, [authAuthenticated])

  useEffect(() => {
    return subscribePushOpenChat(target => {
      setOpenChatTarget(target)
      setMainView('inbox')
      fetchInbox()
      clearOpenChatUrlParams()
    })
  }, [fetchInbox])

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
      if (lead?.status === 'spam') {
        convs.splice(idx, 1)
      } else {
        convs[idx] = patch
      }
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
      wsBackoffRef.current = 1500  // reset backoff on healthy connect
      fetch(`${API}/state?t=${Date.now()}`, { cache: 'no-store' })
        .then(r => (r.ok ? r.json() : null))
        .then(data => { if (data) setState(prev => ({ ...prev, ...data })) })
        .catch(() => {})
      fetchInbox()
      // Notify the inbox panel so it can re-load the currently open chat.
      window.dispatchEvent(new CustomEvent('ws-reconnected'))
    }
    ws.onclose = () => {
      setConnected(false)
      // Exponential backoff with jitter (cap 30s) so a long outage doesn't
      // hammer the server. Reset to 1.5s as soon as a connect succeeds.
      const wait = wsBackoffRef.current
      wsBackoffRef.current = Math.min(30000, Math.floor(wait * 1.7 + Math.random() * 500))
      setTimeout(connect, wait)
    }
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
      if (data.type === 'event' && data.event === 'STATS_RESET' && data.data) {
        setState(prev => {
          const patch = data.data.account_states
          let account_states = prev.account_states
          if (patch && typeof patch === 'object') {
            account_states = { ...prev.account_states }
            for (const [slot, partial] of Object.entries(patch)) {
              account_states[slot] = { ...(account_states[slot] || {}), ...partial }
            }
          }
          return {
            ...prev,
            daily_stats: data.data.daily_stats ?? prev.daily_stats,
            account_states,
          }
        })
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
          inboxLiveQueueRef.current.push({
            slot: data.slot,
            event: data.event,
            message: data.message,
            conversation: data.conversation,
            ts: Date.now(),
          })
          // Cap queue at 200 events to bound memory if InboxPanel is unmounted.
          if (inboxLiveQueueRef.current.length > 200) {
            inboxLiveQueueRef.current.splice(0, inboxLiveQueueRef.current.length - 200)
          }
          setInboxLiveTick(t => t + 1)
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
            block_list: data.crm.block_list || {},
            blocked_count: data.crm.blocked_count ?? 0,
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
      if (data.type === 'voice_call') {
        const session = data.session || {}
        const slot = data.slot || session.account_id
        const userId = data.user_id ?? session.user_id
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
        if (data.conversation && slot) {
          setInboxState(prev => mergeInboxWs(prev, {
            slot,
            event: data.event || 'call_updated',
            conversation: data.conversation,
          }))
        }
        if (data.message && slot) {
          inboxLiveQueueRef.current.push({
            slot,
            event: 'call_event',
            message: data.message,
            conversation: data.conversation,
            ts: Date.now(),
          })
          setInboxLiveTick(t => t + 1)
        }
        window.dispatchEvent(new CustomEvent('voice-call-session', { detail: data }))
        const ev = data.event || ''
        if (ev === 'telegram_answered') {
          window.dispatchEvent(new CustomEvent('voice-call-telegram-answered', { detail: data }))
        } else if (ev === 'telegram_active' || ev === 'active') {
          window.dispatchEvent(new CustomEvent('voice-call-telegram-active', { detail: data }))
        } else if (ev === 'telegram_ended' || ev === 'ended' || ev === 'missed') {
          window.dispatchEvent(new CustomEvent('voice-call-telegram-ended', { detail: data }))
        } else if (ev === 'telegram_failed' || ev === 'failed') {
          window.dispatchEvent(new CustomEvent('voice-call-telegram-failed', { detail: data }))
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

  async function provisionAccountSlot() {
    const res = await fetch(`${API}/accounts/provision-slot`, {
      method: 'POST',
      credentials: 'include',
    })
    const data = await res.json().catch(() => ({}))
    if (data.status !== 'ok' || !data.slot) {
      throw new Error(data.message || data.error || 'Could not add account slot')
    }
    if (Array.isArray(data.account_slots)) {
      setConfiguredSlots(data.account_slots)
    }
    const { type: _t, ...rest } = data
    setState(prev => ({
      ...prev,
      ...rest,
      active_account: data.slot,
    }))
    return data.slot
  }

  async function refreshAccounts() {
    try {
      const res = await fetch(`${API}/state?t=${Date.now()}`, { cache: 'no-store' })
      if (res.ok) {
        const data = await res.json()
        const { type: _t, ...rest } = data
        setState(prev => ({ ...prev, ...rest }))
        return data
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
    return data
  }

  async function handleAccountChange(loginResult) {
    await refreshAccounts()
    if (loginResult?.slot) {
      await switchAccount(loginResult.slot)
    }
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
      if (!quiet && data.partial && data.partial_reason) {
        alert(data.partial_reason)
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
      if ('caches' in window) {
        const keys = await caches.keys()
        await Promise.all(keys.map(k => caches.delete(k)))
      }
    } catch {
      /* ignore cache API errors */
    }
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
    url.searchParams.delete('hard')
    url.searchParams.set('v', `${BUILD_STAMP}-${Date.now()}`)
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
    if (!slot) return
    if (workspaceMode !== WORKSPACE_FLEET) {
      const mode = accountPrimaryMode(state.account_states, slot, state.posting_modes)
      if (mode === 'forwarding') setWorkspaceMode(WORKSPACE_FORWARDING)
      else if (mode === 'campaign') setWorkspaceMode(WORKSPACE_CAMPAIGN)
    }
    setOverviewScope('account')
    const same = slot === state.active_account
    switchAbortRef.current?.abort()
    const controller = new AbortController()
    switchAbortRef.current = controller
    const timeoutId = window.setTimeout(() => controller.abort(), 12000)
    setSwitchingAccount(slot)
    if (!same) {
      setState(prev => ({
        ...prev,
        active_account: slot,
        custom_message: prev.account_messages?.[slot] ?? prev.custom_message,
        ...mirrorActiveAccountFields(prev.account_states?.[slot]),
      }))
    }
    try {
      const res = await fetch(`${API}/account/switch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ slot }),
        signal: controller.signal,
        credentials: 'include',
      })
      if (controller.signal.aborted) return
      const data = await res.json().catch(() => ({}))
      if (!res.ok || data.status === 'error') {
        throw new Error(data.message || `Switch failed (${res.status})`)
      }
      const msgRes = await fetch(`${API}/message?slot=${encodeURIComponent(slot)}`, {
        signal: controller.signal,
        credentials: 'include',
      })
      if (msgRes.ok) {
        const msgData = await msgRes.json()
        if (!controller.signal.aborted) {
          setState(prev => ({ ...prev, custom_message: msgData.message || prev.custom_message }))
        }
      }
    } catch (e) {
      if (e?.name === 'AbortError') return
      /* WebSocket may still sync; keep optimistic selection */
    } finally {
      window.clearTimeout(timeoutId)
      if (switchAbortRef.current === controller) {
        switchAbortRef.current = null
        setSwitchingAccount(null)
      }
    }
  }

  const accountSlots = getAccountSlots(state, configuredSlots)
  const loggedInSlots = useMemo(
    () => getLoggedInSlots(accountSlots, state.account_info),
    [accountSlots, state.account_info],
  )
  const fleet = useMemo(
    () => aggregateFleetStats(state, loggedInSlots, {
      postingModes: state.posting_modes || {},
      modeFilter: workspaceMode === WORKSPACE_FORWARDING
        ? 'forwarding'
        : workspaceMode === WORKSPACE_CAMPAIGN
          ? 'campaign'
          : 'all',
    }),
    [state, loggedInSlots, workspaceMode],
  )
  const sentWindowLabel = state.daily_stats?.window === 'since_reset' ? 'Since reset' : 'Last 24h'
  const inboxUnreadTotal = useMemo(
    () => computeInboxUnreadTotal(inboxState),
    [inboxState],
  )
  const inboxUnreadBadge = formatUnreadBadgeCount(inboxUnreadTotal)

  useEffect(() => {
    syncInboxAlertMusic(inboxUnreadTotal, inboxState)
    syncTabUnreadBadge(inboxUnreadTotal)
    return () => stopInboxAlertMusicOnUnmount()
  }, [inboxUnreadTotal, inboxState])

  useEffect(() => () => resetTabUnreadBadge(), [])

  useEffect(() => {
    const resync = () => syncInboxAlertMusic(inboxUnreadTotal, inboxState)
    window.addEventListener('sound-quiet-hours-change', resync)
    window.addEventListener('crm-buzzer-toggle', resync)
    const tick = window.setInterval(resync, 60000)
    return () => {
      window.removeEventListener('sound-quiet-hours-change', resync)
      window.removeEventListener('crm-buzzer-toggle', resync)
      clearInterval(tick)
    }
  }, [inboxUnreadTotal, inboxState])
  const loggedIn = loggedInSlots.length > 0
  const idleLoggedInSlots = loggedInSlots.filter(
    s => !state.account_states?.[s]?.running
  )
  const canStartMore = idleLoggedInSlots.length > 0

  const workspaceAnyRunning = useMemo(
    () =>
      fleetWorkspaceAnyRunning(
        loggedInSlots,
        state,
        state.posting_modes,
        workspaceMode,
        fleet,
      ),
    [loggedInSlots, state, workspaceMode, fleet],
  )
  const workspaceCanStartMore = useMemo(
    () =>
      fleetWorkspaceCanStartMore(
        loggedInSlots,
        state,
        state.posting_modes,
        workspaceMode,
      ),
    [loggedInSlots, state, workspaceMode],
  )
  const anyProcessRunning = useMemo(
    () =>
      fleetAnyProcessRunning(loggedInSlots, state, state.posting_modes || {}),
    [loggedInSlots, state],
  )

  useEffect(() => {
    if (workspaceBootstrapDoneRef.current || !loggedInSlots.length) return
    workspaceBootstrapDoneRef.current = true
    const synced = resolveWorkspaceSync(
      workspaceMode,
      loggedInSlots,
      state,
      state.posting_modes || {},
    )
    if (synced !== workspaceMode) setWorkspaceMode(synced)
  }, [loggedInSlots, state, workspaceMode])

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
  async function startAccount(slot, oneShot = false, feature = '') {
    const featKey = feature ? `${feature}:` : ''
    setAccountActionLoading(`${slot}:${featKey}start`)
    try {
      const params = new URLSearchParams()
      if (oneShot) params.set('one_shot', 'true')
      if (feature) params.set('feature', feature)
      const qs = params.toString()
      const url = `${API}/account/${slot}/start${qs ? `?${qs}` : ''}`
      await fetch(url, { method: 'POST' })
    } finally {
      setAccountActionLoading(null)
    }
  }
  async function stopAccount(slot, feature = '') {
    const featKey = feature ? `${feature}:` : ''
    setAccountActionLoading(`${slot}:${featKey}stop`)
    try {
      const qs = feature ? `?feature=${encodeURIComponent(feature)}` : ''
      const res = await fetch(`${API}/account/${slot}/stop${qs}`, { method: 'POST' })
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
    // Destructive — confirm so a stray click doesn't wipe a long activity
    // history that the operator may still be cross-referencing.
    const ok = await confirm({
      title: 'Clear logs?',
      message: `All log lines for ${accountLabel(slot)} will be removed from the dashboard. Success / Fail counters are not affected.`,
      variant: 'danger',
      confirmLabel: 'Clear logs',
      cancelLabel: 'Cancel',
    })
    if (!ok) return
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
      const csv = [
        'sno,username',
        ...usernames.map((u, i) => `${i + 1},${csvEscape(u)}`),
      ].join('\n')
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
  const progressView = setupViewForAccountsFilter(
    workspaceMode,
    state.active_account,
    state.account_states,
    state.posting_modes || {},
  )
  const activeFwd = featureRuntime(activeAcctState, 'forwarding')
  const activeCamp = featureRuntime(activeAcctState, 'campaign')
  const displaySuccess = progressView === 'forwarding'
    ? (activeFwd.success ?? 0)
    : progressView === 'campaign'
      ? (activeCamp.success ?? 0)
      : (activeAcctState?.success ?? state.success)
  const displayFailed = progressView === 'forwarding'
    ? (activeFwd.failed ?? 0)
    : progressView === 'campaign'
      ? (activeCamp.failed ?? 0)
      : (activeAcctState?.failed ?? state.failed)
  const displayCurrentGroup = progressView === 'forwarding'
    ? (activeAcctState?.forwarding?.current_group || activeAcctState?.current_group || state.current_group)
    : progressView === 'campaign'
      ? (activeAcctState?.campaign?.current_group || activeAcctState?.current_group || state.current_group)
      : (activeAcctState?.current_group || state.current_group)
  const displayActiveGroups = progressView === 'forwarding'
    ? (activeFwd.active_groups ?? activeAcctState?.active_groups ?? state.active_groups)
    : progressView === 'campaign'
      ? (activeCamp.active_groups ?? activeAcctState?.active_groups ?? state.active_groups)
      : (activeAcctState?.active_groups ?? state.active_groups)
  const displaySkippedPosted = progressView === 'forwarding'
    ? (activeFwd.skipped_already_posted ?? activeAcctState?.skipped_already_posted ?? 0)
    : progressView === 'campaign'
      ? (activeCamp.skipped_already_posted ?? activeAcctState?.skipped_already_posted ?? 0)
      : (activeAcctState?.skipped_already_posted ?? 0)
  const displayTickProcessed = progressView === 'forwarding'
    ? (displaySuccess + displayFailed + displaySkippedPosted)
    : 0
  const displayTickTotal = progressView === 'forwarding'
    ? (Number(displayActiveGroups) || Number(activeAcctState?.forward_batch_size) || 100)
    : 0
  const displayTickRemaining = progressView === 'forwarding'
    ? Math.max(0, displayTickTotal - displayTickProcessed)
    : 0
  const displaySent24h = progressView === 'forwarding'
    ? (activeAcctState?.forward_posts_24h ?? 0)
    : progressView === 'campaign'
      ? (activeAcctState?.campaign_posts_24h ?? 0)
      : (activeAcctState?.messages_sent_24h ?? 0)
  const displaySkippedCooldown = activeAcctState?.skipped_cooldown ?? 0
  const displaySkippedOther = activeAcctState?.skipped_other ?? 0
  const displaySuccessList = activeAcctState?.success_list ?? state.success_list
  const displayFailedList = activeAcctState?.failed_list ?? state.failed_list
  const displaySuccessNewestFirst = useMemo(
    () => [...(displaySuccessList || [])].reverse(),
    [displaySuccessList],
  )
  const displayFailedNewestFirst = useMemo(
    () => [...(displayFailedList || [])].reverse(),
    [displayFailedList],
  )

  const [setupTab, setSetupTab] = useState('setup')

  const shutdownListCount = Object.keys(state.shutdown_list || {}).length

  const setupLoggedInSlots = useMemo(() => {
    const all = getAccountSlots(state, configuredSlots)
    const loggedIn = sortAccountsForDisplay(
      getLoggedInSlots(all, state.account_info || {}),
      state.account_states,
      state.account_info,
    )
    return filterSlotsExcludingShutdown(
      loggedIn,
      state.account_shutdown,
      state.shutdown_list,
    )
  }, [
    state.account_info,
    state.account_states,
    state.account_shutdown,
    state.shutdown_list,
    configuredSlots,
  ])

  const columnSetupView = workspaceMode

  const handleSetupAccountFilter = React.useCallback((filterMode) => {
    setWorkspaceMode(filterMode)
  }, [])

  const handleAccountModeApplied = React.useCallback((mode) => {
    setWorkspaceMode(mode === 'forwarding' ? WORKSPACE_FORWARDING : WORKSPACE_CAMPAIGN)
  }, [])

  useEffect(() => {
    saveWorkspaceMode(workspaceMode)
  }, [workspaceMode])

  useEffect(() => {
    if (workspaceMode === WORKSPACE_FORWARDING && setupTab === 'groups') {
      setSetupTab('setup')
    }
  }, [workspaceMode, setupTab])

  const setupColumnSubtitle = useMemo(() => {
    if (setupTab === 'setup') {
      const slot = state.active_account
      const info = slot && state.account_info?.[slot]
      if (info) {
        return `${telegramDisplayName(info) || accountLabel(slot)} — account → change method → start`
      }
      return 'Pick account → change method → start'
    }
    if (setupTab === 'login') return 'Phone login, add account, rename'
    if (setupTab === 'groups') return 'Upload master group lists (campaign)'
    if (setupTab === 'fleet') {
      return 'Apply the same link or message to every logged-in account'
    }
    if (setupTab === 'shutdown') {
      return shutdownListCount > 0
        ? `${shutdownListCount} resting — clear when ready`
        : 'Accounts on rest after limits'
    }
    return ''
  }, [setupTab, state.active_account, state.account_info, shutdownListCount])

  useEffect(() => {
    if (switchingAccountRef.current) return
    if (setupTab !== 'setup' && setupTab !== 'groups') return
    const first = setupLoggedInSlots[0]
    if (!first) return
    const active = state.active_account
    const ok = active
      && isAccountLoggedIn(state.account_info, active)
      && !isSlotOnShutdownList(state.account_shutdown, state.shutdown_list, active)
    if (!ok) switchAccount(first)
  }, [
    setupTab,
    setupLoggedInSlots,
    state.active_account,
    state.account_info,
    state.account_shutdown,
    state.shutdown_list,
  ])

  const setupTabOptions = useMemo(() => {
    const shutdownLabel = shutdownListCount > 0
      ? `Shutdown (${shutdownListCount})`
      : 'Shutdown'
    const tabs = [
      { value: 'setup', label: 'Setup', role: 'tab' },
      { value: 'login', label: 'Log in', role: 'tab' },
      { value: 'fleet', label: 'Bulk', role: 'tab' },
    ]
    if (workspaceMode === WORKSPACE_CAMPAIGN) {
      tabs.push({ value: 'groups', label: 'Groups', role: 'tab' })
    }
    tabs.push({ value: 'shutdown', label: shutdownLabel, role: 'tab' })
    return tabs
  }, [shutdownListCount, workspaceMode])

  useEffect(() => {
    if (!setupTabOptions.some(t => t.value === setupTab)) {
      const legacyMap = {
        accounts: 'login',
        modes: 'setup',
        forward: 'setup',
        message: 'setup',
      }
      const next = legacyMap[setupTab] || 'setup'
      setSetupTab(setupTabOptions.some(t => t.value === next) ? next : 'setup')
    }
  }, [setupTabOptions, setupTab])

  useEffect(() => {
    const el = logsContainerRef.current
    if (!el) return
    // Keep view pinned to top (newest) unless user scrolled down to read older lines
    if (!userScrolledDown.current) {
      el.scrollTop = 0
    }
  }, [displayLogs, displaySuccessList, displayFailedList, activeTab])

  const total = progressView === 'forwarding'
    ? displaySuccess + displayFailed + displaySkippedPosted
    : displaySuccess + displayFailed
  const successRate = computeSuccessRatePct(displaySuccess, displayFailed)
  const processed = total
  const progressMax = progressView === 'forwarding'
    ? (displayTickTotal || 100)
    : (state.total || 1)
  // skipped = groups where our msg was already last (didn't need sending)
  const skipped = progressView === 'forwarding'
    ? displaySkippedPosted
    : progressMax - (displayActiveGroups || 0)
  // Only show progress if a cycle has actually run
  const hasCycleRun = progressView === 'forwarding'
    ? (activeFwd.cycle ?? 0) > 0
    : (activeAcctState?.cycle ?? 0) > 0
  const progressValue = hasCycleRun
    ? (progressView === 'forwarding'
      ? Math.min(progressMax, displaySuccess + displayFailed + displaySkippedPosted)
      : Math.min(progressMax, skipped + displaySuccess + displayFailed))
    : 0

  const showBootOverlay = initialLoading && !connected
  const compactMobileUi = useMobileShell()
  const [mobilePage, setMobilePage] = useState('home')
  const [desktopPage, setDesktopPage] = useState('home')

  const mobileModesProps = useMemo(
    () => ({
      workspaceMode,
      customMessage:
        (state.active_account && state.account_messages?.[state.active_account])
        ?? state.custom_message
        ?? '',
      rewriteEnabled: state.message_rewrite_enabled,
      cyclePreview: state.cycle_message_preview,
      onMessageSaved: refreshAccounts,
      onPostingModeUpdated: refreshAccounts,
      postingModeConfig: state.account_states?.[state.active_account]?.posting_mode_config,
      postingModes: state.posting_modes,
      accountStates: state.account_states,
      acctRunning: !!state.account_states?.[state.active_account]?.running,
      forwardJob: state.forward_message_jobs?.[state.active_account],
      workerRunning: !!state.account_states?.[state.active_account]?.running,
      loggedIn: !!state.account_info?.[state.active_account],
      onStartAccount: startAccount,
      onStopAccount: stopAccount,
      accountActionLoading,
    }),
    [
      workspaceMode,
      state,
      refreshAccounts,
      startAccount,
      stopAccount,
      accountActionLoading,
    ],
  )

  const desktopTickOverview = useMemo(
    () => ({
      groups: fleet.progressMax,
      sent: fleet.success,
      failed: fleet.failed,
      successRate: fleet.successRate,
      remaining: Math.max(0, fleet.progressMax - fleet.progressValue),
      skipped: fleet.skippedAlreadyPosted,
    }),
    [fleet],
  )

  if (compactMobileUi) {
    return (
      <PendingWorksProvider mainView={mainView}>
        <div
          className={`app-shell app-shell--mobile-ui app-shell--view-${mainView}${showBootOverlay ? ' app-shell--booting' : ''}`}
        >
          <MobileApp
          showBootOverlay={showBootOverlay}
          connected={connected}
          mainView={mainView}
          setMainView={setMainView}
          mobilePage={mobilePage}
          setMobilePage={setMobilePage}
          unlockNotificationSound={unlockNotificationSound}
          fetchInbox={fetchInbox}
          inboxUnreadTotal={inboxUnreadTotal}
          inboxUnreadBadge={inboxUnreadBadge}
          connectedForHeader={connected}
          anyRunning={anyProcessRunning}
          workspaceAnyRunning={workspaceAnyRunning}
          canStartMore={workspaceCanStartMore}
          bulkActionLoading={bulkActionLoading}
          onStartAll={startForwarding}
          onStopAll={stopForwarding}
          hardRefreshing={hardRefreshing}
          onHardRefresh={hardRefresh}
          totalListLoading={totalListLoading}
          onTotalList={buildTotalList}
          authEnabled={authEnabled}
          authUsername={authUsername}
          authLogout={authLogout}
          fleet={fleet}
          globalCountdown={globalCountdown}
          sentWindowLabel={sentWindowLabel}
          state={state}
          loggedInSlots={loggedInSlots}
          postingModes={state.posting_modes}
          workspaceMode={workspaceMode}
          setWorkspaceMode={setWorkspaceMode}
          switchAccount={switchAccount}
          overviewScope={overviewScope}
          onSelectAllAccounts={() => setOverviewScope('fleet')}
          refreshAccounts={refreshAccounts}
          startAccount={startAccount}
          stopAccount={stopAccount}
          accountActionLoading={accountActionLoading}
          setupLoggedInSlots={setupLoggedInSlots}
          handleSetupAccountFilter={handleSetupAccountFilter}
          handleAccountModeApplied={handleAccountModeApplied}
          subscriptionSlots={subscriptionSlots.length ? subscriptionSlots : (state.subscription_slots || [])}
          switchingAccount={switchingAccount}
          setSetupTab={setSetupTab}
          setupTab={setupTab}
          setupTabOptions={setupTabOptions}
          shutdownListCount={shutdownListCount}
          modesProps={mobileModesProps}
          inboxProps={{
            inboxState,
            inboxLiveQueueRef,
            inboxLiveTick,
            accountSlots,
            accountInfo: state.account_info,
            postingModes: state.posting_modes || {},
            crmState,
            onInboxPatch: fetchInbox,
            onCrmUpdate: handleCrmUpdate,
            openChatTarget,
          }}
          logsProps={{
            activeTab,
            activeAccount: state.active_account,
            accountSlots: state.account_slots,
            logScope,
            onLogScopeChange: setLogScope,
            displayLogs,
            displaySuccessList,
            displayFailedList,
            logsContainerRef,
            onScroll: handleLogsScroll,
            connected,
            toolbarActions: (
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
                    text = displayLogsNewestFirst.map(e => {
                      const line = (e.summary || e.fields?.detail || e.msg || '').trim()
                      const lvl = (e.level || 'info').toUpperCase().padEnd(7)
                      const acct = e.account_id ? `[${e.account_id}] ` : ''
                      return `${formatLogTime(e.timestamp || e.time)}  ${lvl} ${acct}${line}`
                    }).join('\n')
                  } else if (activeTab === 'success') {
                    text = displaySuccessNewestFirst.join('\n')
                  } else {
                    text = displayFailedNewestFirst.map(e => `${e.group} — ${e.reason}`).join('\n')
                  }
                  navigator.clipboard.writeText(text).then(() => {
                    setCopied(true)
                    setTimeout(() => setCopied(false), 2000)
                  }).catch(() => {
                    alert('Copy failed — clipboard access blocked by browser.')
                  })
                }}
              />
            ),
            activeTabControl: (
              <LogsToolbarTabs
                activeTab={activeTab}
                setActiveTab={setActiveTab}
                logCount={displayLogs.length}
                okCount={displaySuccessList.length}
                failCount={displayFailedList.length}
              />
            ),
          }}
          progressHubProps={{
            overviewScope,
            accountsModeFilter: workspaceMode,
            onShowFleetOverview: () => setOverviewScope('fleet'),
            fleet,
            globalCountdown,
            sentWindowLabel,
            accountInfo: state.account_info,
            subscriptionSlots: subscriptionSlots.length ? subscriptionSlots : (state.subscription_slots || []),
            dailyStats: state.daily_stats,
            accountSlots,
            onConfirmReset: ({ scope, accountLabel: acctLabel }) =>
              confirm(statsResetConfirmOptions({ scope, accountLabel: acctLabel })),
            onDailyStatsUpdate: (stats, full) => {
              const daily = stats || full?.daily_stats
              if (!daily) return
              setState(prev => {
                const next = { ...prev, daily_stats: daily }
                const incoming = full?.account_states
                if (incoming && prev.account_states) {
                  const account_states = { ...prev.account_states }
                  for (const slot of Object.keys(account_states)) {
                    const patch = incoming[slot]
                    if (!patch?.join_stats) continue
                    account_states[slot] = {
                      ...account_states[slot],
                      join_stats: patch.join_stats,
                    }
                  }
                  next.account_states = account_states
                }
                return next
              })
            },
            activeAccount: state.active_account,
            activeAcctState,
            accountStatus: state.account_status,
            accountShutdown: state.account_shutdown,
            accountStates: state.account_states,
            postingModes: state.posting_modes || {},
            onSelectAccount: switchAccount,
            switchingAccount,
            accountProgress: {
              displaySuccess,
              displayFailed,
              successRate,
              processed,
              displayActiveGroups,
              displayTickTotal,
              displayTickRemaining,
              displaySkippedPosted,
              displaySkippedCooldown,
              displaySkippedOther,
              displaySent24h,
            },
            cycle: {
              displayCurrentGroup,
              countdown,
              cycleElapsed,
              progressValue,
              progressMax,
              hasCycleRun,
            },
            tools: {
              openGroups,
              exportGroupLists,
              loadingGroups,
              exportingKind,
            },
          }}
          confirm={confirm}
          onNavigateExtra={view => {
            unlockNotificationSound()
            setMainView(view)
          }}
          groupsModal={(
            <GroupsModal
              open={showGroups}
              onClose={() => setShowGroups(false)}
              groups={groups}
              loading={loadingGroups}
              onDownload={downloadGroups}
              slotLists={groupsListMeta}
            />
          )}
          incomingCallModal={(
            <IncomingCallModal
              call={incomingCall}
              onDismiss={() => {
                stopIncomingCallRing()
                setIncomingCall(null)
              }}
            />
          )}
        />
        </div>
      </PendingWorksProvider>
    )
  }

  if (!compactMobileUi) {
    return (
      <PendingWorksProvider mainView={mainView}>
        <div
          className={`app-shell app-shell--desktop-ui app-shell--view-${mainView}${showBootOverlay ? ' app-shell--booting' : ''}`}
        >
          <DesktopApp
          showBootOverlay={showBootOverlay}
          connected={connected}
          mainView={mainView}
          setMainView={setMainView}
          desktopPage={desktopPage}
          setDesktopPage={setDesktopPage}
          setWorkspaceMode={setWorkspaceMode}
          workspaceMode={workspaceMode}
          unlockNotificationSound={unlockNotificationSound}
          fetchInbox={fetchInbox}
          inboxUnreadTotal={inboxUnreadTotal}
          inboxUnreadBadge={inboxUnreadBadge}
          anyRunning={anyProcessRunning}
          workspaceAnyRunning={workspaceAnyRunning}
          canStartMore={workspaceCanStartMore}
          bulkActionLoading={bulkActionLoading}
          onStartAll={startForwarding}
          onStopAll={stopForwarding}
          totalListLoading={totalListLoading}
          onTotalList={buildTotalList}
          authUsername={authUsername}
          authEnabled={authEnabled}
          authLogout={authLogout}
          fleet={fleet}
          globalCountdown={globalCountdown}
          sentWindowLabel={sentWindowLabel}
          state={state}
          loggedInSlots={loggedInSlots}
          postingModes={state.posting_modes}
          switchAccount={switchAccount}
          overviewScope={overviewScope}
          onSelectAllAccounts={() => setOverviewScope('fleet')}
          refreshAccounts={refreshAccounts}
          startAccount={startAccount}
          stopAccount={stopAccount}
          accountActionLoading={accountActionLoading}
          shutdownListCount={shutdownListCount}
          setupLoggedInSlots={setupLoggedInSlots}
          handleSetupAccountFilter={handleSetupAccountFilter}
          handleAccountModeApplied={handleAccountModeApplied}
          subscriptionSlots={subscriptionSlots.length ? subscriptionSlots : (state.subscription_slots || [])}
          switchingAccount={switchingAccount}
          setSetupTab={setSetupTab}
          setupTab={setupTab}
          setupTabOptions={setupTabOptions}
          modesProps={mobileModesProps}
          inboxProps={{
            inboxState,
            inboxLiveQueueRef,
            inboxLiveTick,
            accountSlots,
            accountInfo: state.account_info,
            postingModes: state.posting_modes || {},
            crmState,
            onInboxPatch: fetchInbox,
            onCrmUpdate: handleCrmUpdate,
            openChatTarget,
          }}
          logsProps={{
            activeTab,
            activeAccount: state.active_account,
            accountSlots: state.account_slots,
            logScope,
            onLogScopeChange: setLogScope,
            displayLogs,
            displaySuccessList,
            displayFailedList,
            logsContainerRef,
            onScroll: handleLogsScroll,
            connected,
            toolbarActions: (
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
                    text = displayLogsNewestFirst.map(e => {
                      const line = (e.summary || e.fields?.detail || e.msg || '').trim()
                      const lvl = (e.level || 'info').toUpperCase().padEnd(7)
                      const acct = e.account_id ? `[${e.account_id}] ` : ''
                      return `${formatLogTime(e.timestamp || e.time)}  ${lvl} ${acct}${line}`
                    }).join('\n')
                  } else if (activeTab === 'success') {
                    text = displaySuccessNewestFirst.join('\n')
                  } else {
                    text = displayFailedNewestFirst.map(e => `${e.group} — ${e.reason}`).join('\n')
                  }
                  navigator.clipboard.writeText(text).then(() => {
                    setCopied(true)
                    setTimeout(() => setCopied(false), 2000)
                  }).catch(() => {
                    alert('Copy failed — clipboard access blocked by browser.')
                  })
                }}
              />
            ),
            activeTabControl: (
              <LogsToolbarTabs
                activeTab={activeTab}
                setActiveTab={setActiveTab}
                logCount={displayLogs.length}
                okCount={displaySuccessList.length}
                failCount={displayFailedList.length}
              />
            ),
          }}
          progressHubProps={{
            overviewScope,
            accountsModeFilter: workspaceMode,
            onShowFleetOverview: () => setOverviewScope('fleet'),
            fleet,
            globalCountdown,
            sentWindowLabel,
            accountInfo: state.account_info,
            subscriptionSlots: subscriptionSlots.length ? subscriptionSlots : (state.subscription_slots || []),
            dailyStats: state.daily_stats,
            accountSlots,
            onConfirmReset: ({ scope, accountLabel: acctLabel }) =>
              confirm(statsResetConfirmOptions({ scope, accountLabel: acctLabel })),
            onDailyStatsUpdate: (stats, full) => {
              const daily = stats || full?.daily_stats
              if (!daily) return
              setState(prev => {
                const next = { ...prev, daily_stats: daily }
                const incoming = full?.account_states
                if (incoming && prev.account_states) {
                  const account_states = { ...prev.account_states }
                  for (const slot of Object.keys(account_states)) {
                    const patch = incoming[slot]
                    if (!patch?.join_stats) continue
                    account_states[slot] = {
                      ...account_states[slot],
                      join_stats: patch.join_stats,
                    }
                  }
                  next.account_states = account_states
                }
                return next
              })
            },
            activeAccount: state.active_account,
            activeAcctState,
            accountStatus: state.account_status,
            accountShutdown: state.account_shutdown,
            accountStates: state.account_states,
            postingModes: state.posting_modes || {},
            onSelectAccount: switchAccount,
            switchingAccount,
            accountProgress: {
              displaySuccess,
              displayFailed,
              successRate,
              processed,
              displayActiveGroups,
              displayTickTotal,
              displayTickRemaining,
              displaySkippedPosted,
              displaySkippedCooldown,
              displaySkippedOther,
              displaySent24h,
            },
            cycle: {
              displayCurrentGroup,
              countdown,
              cycleElapsed,
              progressValue,
              progressMax,
              hasCycleRun,
            },
            tools: {
              openGroups,
              exportGroupLists,
              loadingGroups,
              exportingKind,
            },
          }}
          confirm={confirm}
          setupPanelProps={{
            accountPanel: {
              state,
              configuredSlots,
              subscriptionSlots: subscriptionSlots.length ? subscriptionSlots : (state.subscription_slots || []),
              // Log in tab lists every working account (campaign + forwarding), not just the active workspace mode.
              accountsModeFilter: 'all',
              onAccountsModeFilterChange: setWorkspaceMode,
              hideAccountsModeFilter: true,
              workspaceMode,
              onAccountChange: handleAccountChange,
              onStartAccount: startAccount,
              onStopAccount: stopAccount,
              onSwitchAccount: switchAccount,
              onRefreshJoined: refreshJoinedCounts,
              refreshingJoinedSlot,
              accountActionLoading,
              switchingAccount,
              onMessageSaved: refreshAccounts,
              onPostingModeUpdated: refreshAccounts,
              onShutdownUpdated: refreshAccounts,
              onRenamed: (slot, accountInfo) => {
                if (!slot || !accountInfo) return
                setState(prev => ({
                  ...prev,
                  account_info: { ...prev.account_info, [slot]: accountInfo },
                }))
              },
              onProvisionSlot: provisionAccountSlot,
              compactSetup: true,
              showShutdown: false,
              overviewScope,
              onShowFleetOverview: () => setOverviewScope('fleet'),
              onOpenFleetTab: () => {
                setSetupTab('fleet')
                setOverviewScope('fleet')
              },
            },
          }}
          groupsUploadProps={{
            currentTotal: state.total || 0,
            fleetSliceTotal: fleet.fleetSliceTotal ?? 0,
            activeAccountSlice: state.active_account
              ? (state.account_states?.[state.active_account]?.my_groups?.length ?? 0)
              : null,
            onUpdated: refreshAccounts,
            listSummary: groupsListMeta
              ? { active: groupsListMeta.active_count, dead: groupsListMeta.dead_count }
              : null,
          }}
          tickOverview={desktopTickOverview}
          recentLogs={displayLogsNewestFirst}
          groupsModal={(
            <GroupsModal
              open={showGroups}
              onClose={() => setShowGroups(false)}
              groups={groups}
              loading={loadingGroups}
              onDownload={downloadGroups}
              slotLists={groupsListMeta}
            />
          )}
          incomingCallModal={(
            <IncomingCallModal
              call={incomingCall}
              onDismiss={() => {
                stopIncomingCallRing()
                setIncomingCall(null)
              }}
            />
          )}
        />
        </div>
      </PendingWorksProvider>
    )
  }

  return (
    <div className={`app-shell app-shell--view-${mainView}${showBootOverlay ? ' app-shell--booting' : ''}`}>
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
                  · Viewing {telegramDisplayName(state.account_info[state.active_account])}
                </span>
              )}
            </p>
          </div>
        </div>

        <div className="app-header-right">
          <div className="app-header-toolbar">
            {authEnabled ? (
              <div
                className="app-header-auth"
                title={`Signed in as ${authUsername || 'operator'}`}
              >
                <div className="app-header-auth-user">
                  <span className="app-header-auth-avatar" aria-hidden>
                    {(authUsername || 'op').slice(0, 2).toUpperCase()}
                  </span>
                  <span className="app-header-auth-name">{authUsername || 'operator'}</span>
                </div>
                <button
                  type="button"
                  className="app-header-auth-signout"
                  onClick={() => authLogout()}
                  aria-label={`Sign out ${authUsername || 'operator'}`}
                >
                  Sign out
                </button>
              </div>
            ) : (
              <span className="app-header-toolbar__spacer" aria-hidden />
            )}
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
          <AppViewNav
            mainView={mainView}
            inboxUnreadTotal={inboxUnreadTotal}
            inboxUnreadBadge={inboxUnreadBadge}
            handlerMode={authRole === 'handler'}
            onNavigate={view => {
              if (view === 'dashboard') unlockNotificationSound()
              if (view === 'inbox') fetchInbox()
              setMainView(view)
            }}
          />
        </div>
      </header>

      {mainView === 'inbox' ? (
        <InboxPanel
          inboxState={inboxState}
          inboxLiveQueueRef={inboxLiveQueueRef}
          inboxLiveTick={inboxLiveTick}
          accountSlots={accountSlots}
          accountInfo={state.account_info}
          postingModes={state.posting_modes || {}}
          crmState={crmState}
          onInboxPatch={fetchInbox}
          onCrmUpdate={handleCrmUpdate}
          onBackToDashboard={() => setMainView('dashboard')}
          openChatTarget={openChatTarget}
        />
      ) : mainView === 'handler-kit' ? (
        <HandlerKitPanel username={authUsername} reference={authReference} />
      ) : mainView === 'candidates' ? (
        <CandidatesPanel />
      ) : mainView === 'data-room' ? (
        <DataRoomPanel />
      ) : mainView === 'admin' ? (
        <AdminPanel />
      ) : mainView === 'logs' ? (
        <div className="logs-fullpage">
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
            connected={connected}
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
                    text = displayLogsNewestFirst.map(e => {
                      const line = (e.summary || e.fields?.detail || e.msg || '').trim()
                      const lvl = (e.level || 'info').toUpperCase().padEnd(7)
                      const acct = e.account_id ? `[${e.account_id}] ` : ''
                      return `${formatLogTime(e.timestamp || e.time)}  ${lvl} ${acct}${line}`
                    }).join('\n')
                  } else if (activeTab === 'success') {
                    text = displaySuccessNewestFirst.join('\n')
                  } else {
                    text = displayFailedNewestFirst.map(e => `${e.group} — ${e.reason}`).join('\n')
                  }
                  navigator.clipboard.writeText(text).then(() => {
                    setCopied(true)
                    setTimeout(() => setCopied(false), 2000)
                  }).catch(() => {
                    alert('Copy failed — clipboard access blocked by browser.')
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
        </div>
      ) : (
      <ResizableDashboardLayout
        left={(
        <DashboardColumn
          id="left"
          title="Setup"
          subtitle={setupColumnSubtitle}
        >
          <div className={`setup-column setup-column--${workspaceMode}`}>
            <div className="setup-column-nav" aria-label="Setup menu">
              <ResponsiveOptions
                className="setup-column-nav__tabs-wrap"
                segmentedClassName="setup-column-nav__tabs setup-column-tabs"
                label="Setup menu"
                options={setupTabOptions}
                value={setupTab}
                onChange={setSetupTab}
                role="tablist"
                compactColumns={2}
              />
            </div>
            <div className="setup-column-panels">
              <div
                className={`setup-column-panel${setupTab === 'setup' ? ' setup-column-panel--active' : ''}`}
                role="tabpanel"
                hidden={setupTab !== 'setup'}
                aria-hidden={setupTab !== 'setup'}
              >
                <div className="setup-column-panel__scroll">
                  <SetupMainPanel
                    slots={setupLoggedInSlots}
                    accountFilter={workspaceMode}
                    onAccountFilterChange={handleSetupAccountFilter}
                    onModeApplied={handleAccountModeApplied}
                    activeSlot={state.active_account}
                    accountInfo={state.account_info}
                    accountStates={state.account_states}
                    postingModes={state.posting_modes}
                    accountShutdown={state.account_shutdown}
                    subscriptionSlots={subscriptionSlots.length ? subscriptionSlots : (state.subscription_slots || [])}
                    switchingAccount={switchingAccount}
                    onSelectAccount={switchAccount}
                    onOpenLoginTab={() => setSetupTab('login')}
                    onPostingModeUpdated={refreshAccounts}
                    modesProps={{
                      workspaceMode,
                      customMessage:
                        (state.active_account && state.account_messages?.[state.active_account])
                        ?? state.custom_message
                        ?? '',
                      rewriteEnabled: state.message_rewrite_enabled,
                      cyclePreview: state.cycle_message_preview,
                      onMessageSaved: refreshAccounts,
                      onPostingModeUpdated: refreshAccounts,
                      postingModeConfig: state.account_states?.[state.active_account]?.posting_mode_config,
                      postingModes: state.posting_modes,
                      accountStates: state.account_states,
                      acctRunning: !!state.account_states?.[state.active_account]?.running,
                      forwardJob: state.forward_message_jobs?.[state.active_account],
                      workerRunning: !!state.account_states?.[state.active_account]?.running,
                      loggedIn: !!state.account_info?.[state.active_account],
                      onStartAccount: startAccount,
                      onStopAccount: stopAccount,
                      accountActionLoading,
                    }}
                  />
                </div>
              </div>
              <div
                className={`setup-column-panel${setupTab === 'login' ? ' setup-column-panel--active' : ''}`}
                role="tabpanel"
                hidden={setupTab !== 'login'}
                aria-hidden={setupTab !== 'login'}
              >
                <div className="setup-column-panel__scroll">
                  <AccountPanel
                    state={state}
                    configuredSlots={configuredSlots}
                    subscriptionSlots={subscriptionSlots.length ? subscriptionSlots : (state.subscription_slots || [])}
                    accountsModeFilter="all"
                    onAccountsModeFilterChange={setWorkspaceMode}
                    hideAccountsModeFilter
                    workspaceMode={workspaceMode}
                    onAccountChange={handleAccountChange}
                    onStartAccount={startAccount}
                    onStopAccount={stopAccount}
                    onSwitchAccount={switchAccount}
                    onRefreshJoined={refreshJoinedCounts}
                    refreshingJoinedSlot={refreshingJoinedSlot}
                    accountActionLoading={accountActionLoading}
                    switchingAccount={switchingAccount}
                    onMessageSaved={refreshAccounts}
                    onPostingModeUpdated={refreshAccounts}
                    onShutdownUpdated={refreshAccounts}
                    onRenamed={(slot, accountInfo) => {
                      if (!slot || !accountInfo) return
                      setState(prev => ({
                        ...prev,
                        account_info: {
                          ...prev.account_info,
                          [slot]: accountInfo,
                        },
                      }))
                    }}
                    onProvisionSlot={provisionAccountSlot}
                    compactSetup
                    showShutdown={false}
                    overviewScope={overviewScope}
                    onShowFleetOverview={() => setOverviewScope('fleet')}
                    onOpenFleetTab={() => {
                      setSetupTab('fleet')
                      setOverviewScope('fleet')
                    }}
                  />
                </div>
              </div>
              <div
                className={`setup-column-panel setup-column-panel--fleet${setupTab === 'fleet' ? ' setup-column-panel--active' : ''}`}
                role="tabpanel"
                hidden={setupTab !== 'fleet'}
                aria-hidden={setupTab !== 'fleet'}
              >
                <div className="setup-column-panel__scroll setup-column-panel__scroll--fleet">
                  <FleetDefaultsPanel
                    embedInTab
                    workspaceMode={workspaceMode}
                    loggedInCount={setupLoggedInSlots.length}
                    onUpdated={refreshAccounts}
                  />
                </div>
              </div>
              <div
                className={`setup-column-panel${setupTab === 'groups' ? ' setup-column-panel--active' : ''}`}
                role="tabpanel"
                hidden={setupTab !== 'groups'}
                aria-hidden={setupTab !== 'groups'}
              >
                <div className="setup-column-panel__scroll">
                  <SetupAccountPicker
                    slots={setupLoggedInSlots}
                    activeSlot={state.active_account}
                    accountInfo={state.account_info}
                    accountStates={state.account_states}
                    postingModes={state.posting_modes}
                    accountShutdown={state.account_shutdown}
                    subscriptionSlots={subscriptionSlots.length ? subscriptionSlots : (state.subscription_slots || [])}
                    switchingAccount={switchingAccount}
                    onSelect={switchAccount}
                    onOpenAccountsTab={() => setSetupTab('login')}
                  />
                  <GroupsUpload
                    currentTotal={state.total || 0}
                    fleetSliceTotal={fleet.fleetSliceTotal ?? 0}
                    activeAccountSlice={
                      state.active_account
                        ? (state.account_states?.[state.active_account]?.my_groups?.length ?? 0)
                        : null
                    }
                    onUpdated={refreshAccounts}
                    listSummary={groupsListMeta ? {
                      active: groupsListMeta.active_count,
                      dead: groupsListMeta.dead_count,
                    } : null}
                  />
                </div>
              </div>
              <div
                className={`setup-column-panel${setupTab === 'shutdown' ? ' setup-column-panel--active' : ''}`}
                role="tabpanel"
                hidden={setupTab !== 'shutdown'}
                aria-hidden={setupTab !== 'shutdown'}
              >
                <div className="setup-column-panel__scroll">
                  <ShutdownListPanel
                    shutdownList={state.shutdown_list}
                    accountShutdown={state.account_shutdown}
                    accountInfo={state.account_info}
                    onUpdated={refreshAccounts}
                    embedInTab
                  />
                </div>
              </div>
            </div>
          </div>
        </DashboardColumn>
        )}
        center={(
        <DashboardColumn
          id="center"
          title="Progress"
          subtitle={
            overviewScope === 'account' && state.active_account
              ? accountLabel(state.active_account)
              : SABHI_ACCOUNTS
          }
          flush
        >
          <ProgressHubPanel
            overviewScope={overviewScope}
            accountsModeFilter={workspaceMode}
            onShowFleetOverview={() => setOverviewScope('fleet')}
            fleet={fleet}
            globalCountdown={globalCountdown}
            sentWindowLabel={sentWindowLabel}
            accountInfo={state.account_info}
            subscriptionSlots={subscriptionSlots.length ? subscriptionSlots : (state.subscription_slots || [])}
            dailyStats={state.daily_stats}
            accountSlots={accountSlots}
            onConfirmReset={({ scope, accountLabel: acctLabel }) =>
              confirm(
                statsResetConfirmOptions({ scope, accountLabel: acctLabel }),
              )}
            onDailyStatsUpdate={(stats, full) => {
              const daily = stats || full?.daily_stats
              if (!daily) return
              setState(prev => {
                const next = { ...prev, daily_stats: daily }
                // Stats reset must not replace worker logs / cycle UI from a full state snapshot.
                const incoming = full?.account_states
                if (incoming && prev.account_states) {
                  const account_states = { ...prev.account_states }
                  for (const slot of Object.keys(account_states)) {
                    const patch = incoming[slot]
                    if (!patch?.join_stats) continue
                    account_states[slot] = {
                      ...account_states[slot],
                      join_stats: patch.join_stats,
                    }
                  }
                  next.account_states = account_states
                }
                return next
              })
            }}
            activeAccount={state.active_account}
            activeAcctState={activeAcctState}
            accountStatus={state.account_status}
            accountShutdown={state.account_shutdown}
            accountStates={state.account_states}
            postingModes={state.posting_modes || {}}
            onSelectAccount={switchAccount}
            switchingAccount={switchingAccount}
            accountProgress={{
              displaySuccess,
              displayFailed,
              successRate,
              processed,
              displayActiveGroups,
              displayTickTotal,
              displayTickRemaining,
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
        right={null}
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
