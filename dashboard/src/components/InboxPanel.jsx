import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { API } from '../config.js'
import { accountLabel } from '../utils/accountUi.js'
import { CRM_STATUS_SPAM, markReplyHandled, patchLead, scheduleFollowUp, unblockLead } from '../utils/crm.js'
import {
  REPLY_CHECK_INTERVAL_MS,
  countAlertConversationsByLevel,
  formatUrgentTopBanner,
} from '../utils/replyAlert.js'
import { sortConversationsByUrgency, callChannelLabel } from '../utils/leadUx.js'
import { syncReplyAlerts, stopReplyBuzzerOnUnmount } from '../utils/replyBuzzerSound.js'
import { CrmBuzzerToggle } from './crm/CrmBuzzerToggle.jsx'
import {
  buildCallLink,
  buildCallSystemMessage,
  buildLiveCallInitiatedMessage,
  completeCall,
  getScheduledCall,
  initiateLiveCall,
  scheduleCall,
} from '../utils/calls.js'
import {
  playNewMessageSound,
  unlockNotificationSound,
  startIncomingCallRing,
} from '../utils/notificationSound.js'
import {
  LIVE_EVENTS,
  appendMessageDeduped,
  applyMessageStatus,
  applyOutboundLiveMessage,
  applyReadUpTo,
  isUserNearBottom,
  mergeMessageLists,
  replacePendingMessage,
  sameUser,
} from '../utils/inboxMessageUtils.js'
import { CallOutcomeModal } from './crm/CallOutcomeModal.jsx'
import { CallReminderBanner } from './crm/CallReminderBanner.jsx'
import { ChatWindow } from './crm/ChatWindow.jsx'
import { CRMInboxList } from './crm/CRMInboxList.jsx'
import { CrmStatsBar } from './crm/CrmStatsBar.jsx'
import { LeadDetailsPanel } from './crm/LeadDetailsPanel.jsx'
import { CallNowModal } from './crm/CallNowModal.jsx'
import { ScheduleCallModal } from './crm/ScheduleCallModal.jsx'

export function InboxPanel({
  inboxState,
  inboxLiveEvent,
  onInboxPatch,
  accountSlots,
  crmState,
  onCrmUpdate,
}) {
  const [mode, setMode] = useState('combined')
  const [filterSlot, setFilterSlot] = useState(accountSlots[0] || 'account1')
  const [crmFilter, setCrmFilter] = useState('all')
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState(null)
  const [messages, setMessages] = useState([])
  const [loadingMessages, setLoadingMessages] = useState(false)
  const [replyText, setReplyText] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const [showNewMessages, setShowNewMessages] = useState(false)
  const [notes, setNotes] = useState('')
  const [crmSaving, setCrmSaving] = useState(false)
  const [followUpLoading, setFollowUpLoading] = useState(false)
  const [scheduleModalOpen, setScheduleModalOpen] = useState(false)
  const [callNowOpen, setCallNowOpen] = useState(false)
  const [callNowLoading, setCallNowLoading] = useState(false)
  const [callScheduling, setCallScheduling] = useState(false)
  const [outcomeCall, setOutcomeCall] = useState(null)
  const [outcomeSaving, setOutcomeSaving] = useState(false)
  const alertedCallIdsRef = useRef(new Set())
  const skippedOutcomeIdsRef = useRef(new Set())
  const [replyCheckTick, setReplyCheckTick] = useState(0)
  const [toast, setToast] = useState(null)

  const loadSeqRef = useRef(0)
  const sendingRef = useRef(false)
  const messagesScrollRef = useRef(null)
  const messagesEndRef = useRef(null)
  const stickToBottomRef = useRef(true)
  const forceScrollRef = useRef(false)
  const lastMessageCountRef = useRef(0)
  const onInboxPatchRef = useRef(onInboxPatch)
  onInboxPatchRef.current = onInboxPatch

  const leadDetail = useMemo(() => {
    if (!selected) return null
    const key = `${selected.slot}:${selected.user_id}`
    const lead = crmState?.leads?.[key] || null
    const call = getScheduledCall(crmState, selected.slot, selected.user_id)
    if (!lead) return call ? { scheduled_call: call } : null
    return { ...lead, scheduled_call: call || lead.scheduled_call }
  }, [selected, crmState?.leads, crmState?.scheduled_calls])

  useEffect(() => {
    if (leadDetail) {
      setNotes(leadDetail.notes || '')
    } else {
      setNotes('')
    }
  }, [leadDetail?.notes, selected?.slot, selected?.user_id])

  const snapScrollToBottom = useCallback(() => {
    const el = messagesScrollRef.current
    if (!el) return
    el.scrollTop = Math.max(0, el.scrollHeight - el.clientHeight)
  }, [])

  const scrollToBottom = useCallback(({ smooth = false } = {}) => {
    const el = messagesScrollRef.current
    if (!el) return
    if (smooth) {
      el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
    } else {
      snapScrollToBottom()
    }
  }, [snapScrollToBottom])

  const jumpToLatest = useCallback(() => {
    stickToBottomRef.current = true
    forceScrollRef.current = true
    setShowNewMessages(false)
    scrollToBottom({ smooth: false })
  }, [scrollToBottom])

  const jumpToInbound = useCallback(() => {
    const el = messagesScrollRef.current
    if (!el) return
    stickToBottomRef.current = false
    setShowNewMessages(false)
    const first = el.querySelector('.inbox-bubble--in')
    if (first) {
      first.scrollIntoView({ block: 'center', behavior: 'smooth' })
      return
    }
    el.scrollTop = 0
  }, [])

  const handleMessagesScroll = useCallback(() => {
    const el = messagesScrollRef.current
    if (!el) return
    stickToBottomRef.current = isUserNearBottom(el)
    if (stickToBottomRef.current) setShowNewMessages(false)
  }, [])

  const selectConversation = useCallback((c) => {
    unlockNotificationSound()
    setSelected({ slot: c.account_id, user_id: c.user_id })
    setReplyText('')
    setError('')
    stickToBottomRef.current = true
    forceScrollRef.current = true
    setShowNewMessages(false)
  }, [])

  const conversations = useMemo(() => {
    if (!inboxState?.slots) return []
    if (mode === 'combined') {
      const list = []
      for (const slot of accountSlots) {
        const block = inboxState.slots[slot]
        if (!block?.conversations) continue
        for (const c of block.conversations) {
          list.push({ ...c, account_id: slot })
        }
      }
      return sortConversationsByUrgency(list)
    }
    return sortConversationsByUrgency(
      (inboxState.slots[filterSlot]?.conversations || []).map(c => ({
        ...c,
        account_id: filterSlot,
      })),
    )
  }, [inboxState, mode, filterSlot, accountSlots, replyCheckTick])

  const alertCounts = useMemo(
    () => countAlertConversationsByLevel(inboxState),
    [inboxState, replyCheckTick],
  )

  useEffect(() => {
    syncReplyAlerts(inboxState)
    return () => stopReplyBuzzerOnUnmount()
  }, [inboxState, alertCounts.total, alertCounts.aggressive, alertCounts.buzzer])

  useEffect(() => {
    const id = window.setInterval(() => setReplyCheckTick(t => t + 1), REPLY_CHECK_INTERVAL_MS)
    const resync = () => setReplyCheckTick(t => t + 1)
    window.addEventListener('crm-buzzer-toggle', resync)
    window.addEventListener('sound-quiet-hours-change', resync)
    return () => {
      clearInterval(id)
      window.removeEventListener('crm-buzzer-toggle', resync)
      window.removeEventListener('sound-quiet-hours-change', resync)
    }
  }, [])

  const selectedConv = conversations.find(
    c => selected
      && c.account_id === selected.slot
      && sameUser(c.user_id, selected.user_id),
  )

  const selectedCall = useMemo(() => {
    if (!selected) return null
    return getScheduledCall(crmState, selected.slot, selected.user_id)
      || selectedConv?.crm_scheduled_call
      || null
  }, [selected, selectedConv, crmState?.scheduled_calls])

  useEffect(() => {
    if (!selected || !inboxLiveEvent) return
    if (!LIVE_EVENTS.has(inboxLiveEvent.event)) return
    if (inboxLiveEvent.slot !== selected.slot) return
    const uid = inboxLiveEvent.conversation?.user_id ?? inboxLiveEvent.message?.user_id
    if (uid != null && !sameUser(uid, selected.user_id)) return

    if (inboxLiveEvent.event === 'message_read') {
      setMessages(prev => applyReadUpTo(prev, inboxLiveEvent.message?.max_id))
      return
    }
    if (inboxLiveEvent.event === 'message_status') {
      setMessages(prev => applyMessageStatus(prev, inboxLiveEvent.message))
      return
    }
    if (!inboxLiveEvent.message) return

    const msg = inboxLiveEvent.message
    if (msg.direction === 'in' || inboxLiveEvent.event === 'new_message') {
      setMessages(prev => appendMessageDeduped(prev, msg))
      stickToBottomRef.current = true
      forceScrollRef.current = true
      return
    }
    setMessages(prev => applyOutboundLiveMessage(prev, msg))
  }, [inboxLiveEvent, selected])

  useEffect(() => {
    const el = messagesScrollRef.current
    const prevCount = lastMessageCountRef.current
    const count = messages.length
    lastMessageCountRef.current = count
    const grew = count > prevCount

    const runScrollDecision = () => {
      const force = forceScrollRef.current
      forceScrollRef.current = false
      if (force || loadingMessages) {
        scrollToBottom({ smooth: false })
        stickToBottomRef.current = true
        setShowNewMessages(false)
        return
      }
      if (!grew) return
      const near = stickToBottomRef.current || (el ? isUserNearBottom(el) : false)
      stickToBottomRef.current = near
      if (near) {
        scrollToBottom({ smooth: false })
        setShowNewMessages(false)
      } else {
        setShowNewMessages(true)
      }
    }
    requestAnimationFrame(() => requestAnimationFrame(runScrollDecision))
  }, [messages, selected, scrollToBottom, loadingMessages])

  useEffect(() => {
    if (!selected || loadingMessages || messages.length === 0) return
    stickToBottomRef.current = true
    forceScrollRef.current = true
    setShowNewMessages(false)
  }, [loadingMessages, selected?.slot, selected?.user_id, messages.length])

  useEffect(() => {
    if (!selected) {
      setMessages([])
      setError('')
      setReplyText('')
      return undefined
    }
    const { slot, user_id: userId } = selected
    const seq = ++loadSeqRef.current
    setMessages([])
    setLoadingMessages(true)
    setError('')
    const controller = new AbortController()
    const applyMessages = (data, { merge = false } = {}) => {
      if (seq !== loadSeqRef.current) return
      if (data.status !== 'ok') {
        setError(data.message || 'Failed to load messages')
        return
      }
      const rows = data.messages || []
      if (merge) {
        setMessages(prev => mergeMessageLists(rows, prev))
      } else {
        setMessages(rows)
      }
    }
    ;(async () => {
      try {
        const fastRes = await fetch(
          `${API}/inbox/${encodeURIComponent(slot)}/messages/${userId}?sync=0`,
          { signal: controller.signal, cache: 'no-store' },
        )
        if (!fastRes.ok) throw new Error(fastRes.status === 404 ? 'Not found' : `HTTP ${fastRes.status}`)
        applyMessages(await fastRes.json(), { merge: false })
      } catch (e) {
        if (seq !== loadSeqRef.current || e.name === 'AbortError') return
        setError(e.message?.includes('fetch') ? 'Could not reach server' : e.message)
      } finally {
        if (seq === loadSeqRef.current) setLoadingMessages(false)
      }
      if (seq !== loadSeqRef.current) return
      try {
        const fullRes = await fetch(
          `${API}/inbox/${encodeURIComponent(slot)}/messages/${userId}?sync=1`,
          { signal: controller.signal, cache: 'no-store' },
        )
        if (!fullRes.ok) return
        applyMessages(await fullRes.json(), { merge: true })
      } catch {
        /* Telegram sync optional */
      }
    })()
    return () => controller.abort()
  }, [selected?.slot, selected?.user_id])

  useEffect(() => {
    if (!selected || !selectedConv?.last_message_at || loadingMessages) return undefined
    const { slot, user_id: userId } = selected
    const controller = new AbortController()
    ;(async () => {
      try {
        const res = await fetch(
          `${API}/inbox/${encodeURIComponent(slot)}/messages/${userId}?sync=0`,
          { signal: controller.signal, cache: 'no-store' },
        )
        if (!res.ok) return
        const data = await res.json()
        if (data.status === 'ok' && Array.isArray(data.messages)) {
          setMessages(prev => mergeMessageLists(data.messages, prev))
        }
      } catch {
        /* ignore background refresh errors */
      }
    })()
    return () => controller.abort()
  }, [selected?.slot, selected?.user_id, selectedConv?.last_message_at, loadingMessages])

  useEffect(() => {
    if (mode === 'per_account' && filterSlot && selected && selected.slot !== filterSlot) {
      setSelected(null)
    }
  }, [mode, filterSlot, selected])

  async function sendReply() {
    if (!selected || !replyText.trim() || sendingRef.current) return
    const text = replyText.trim()
    const pendingId = `pending-${Date.now()}`
    const optimistic = {
      id: pendingId,
      chat_id: selected.user_id,
      account_id: selected.slot,
      direction: 'out',
      text,
      timestamp: new Date().toISOString(),
      status: 'sending',
      read_at: null,
    }
    sendingRef.current = true
    setSending(true)
    setError('')
    stickToBottomRef.current = true
    forceScrollRef.current = true
    setShowNewMessages(false)
    setMessages(prev => [...prev, optimistic])
    setReplyText('')
    try {
      const res = await fetch(`${API}/inbox/${encodeURIComponent(selected.slot)}/reply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: selected.user_id, text }),
      })
      const data = await res.json()
      if (data.status !== 'ok') {
        setError(data.message || 'Send failed')
        setMessages(prev => prev.map(m => (m.id === pendingId ? { ...m, status: 'failed' } : m)))
        return
      }
      if (data.message) {
        setMessages(prev => replacePendingMessage(prev, pendingId, data.message))
      }
      if (data.lead) {
        onCrmUpdate?.(null, data.lead)
      } else {
        const replyAt = data.message?.timestamp || new Date().toISOString()
        onCrmUpdate?.(null, {
          account_id: selected.slot,
          user_id: Number(selected.user_id),
          last_reply_at: replyAt,
          last_user_message_at:
            selectedConv?.crm_last_user_message_at
            ?? selectedConv?.last_user_message_at
            ?? null,
        })
      }
      onInboxPatchRef.current?.()
    } catch (e) {
      setError(String(e.message || e))
      setMessages(prev => prev.map(m => (m.id === pendingId ? { ...m, status: 'failed' } : m)))
    } finally {
      sendingRef.current = false
      setSending(false)
    }
  }

  async function handleStatusChange(status) {
    if (!selected) return
    setCrmSaving(true)
    try {
      const data = await patchLead(selected.slot, selected.user_id, { status })
      onCrmUpdate?.(data.crm, data.lead)
    } catch (e) {
      setError(String(e.message || e))
    } finally {
      setCrmSaving(false)
    }
  }

  async function handleSaveNotes() {
    if (!selected) return
    setCrmSaving(true)
    try {
      const data = await patchLead(selected.slot, selected.user_id, { notes })
      onCrmUpdate?.(data.crm, data.lead)
    } catch (e) {
      setError(String(e.message || e))
    } finally {
      setCrmSaving(false)
    }
  }

  async function handleMarkHandled() {
    if (!selected) return
    setCrmSaving(true)
    try {
      const data = await markReplyHandled(selected.slot, selected.user_id)
      onCrmUpdate?.(data.crm, data.lead)
    } catch (e) {
      setError(String(e.message || e))
    } finally {
      setCrmSaving(false)
    }
  }

  async function handleMarkSpam() {
    if (!selected) return
    setCrmSaving(true)
    try {
      const data = await patchLead(selected.slot, selected.user_id, { status: CRM_STATUS_SPAM })
      onCrmUpdate?.(data.crm, data.lead)
    } catch (e) {
      setError(String(e.message || e))
    } finally {
      setCrmSaving(false)
    }
  }

  async function handleUnblock() {
    if (!selected) return
    setCrmSaving(true)
    try {
      const data = await unblockLead(selected.slot, selected.user_id)
      onCrmUpdate?.(data.crm, data.lead)
    } catch (e) {
      setError(String(e.message || e))
    } finally {
      setCrmSaving(false)
    }
  }

  useEffect(() => {
    const reminders = crmState?.call_reminders || []
    for (const r of reminders) {
      const id = r.id || `${r.account_id}:${r.user_id}`
      if (alertedCallIdsRef.current.has(id)) continue
      alertedCallIdsRef.current.add(id)
      unlockNotificationSound()
      startIncomingCallRing()
    }
  }, [crmState?.call_reminders])

  useEffect(() => {
    if (outcomeCall) return
    const past = crmState?.past_due_calls || []
    const next = past.find(
      c => c.id && !skippedOutcomeIdsRef.current.has(c.id),
    )
    if (next) setOutcomeCall(next)
  }, [crmState?.past_due_calls, outcomeCall])

  const openScheduleCallModal = useCallback(() => {
    unlockNotificationSound()
    setError('')
    setScheduleModalOpen(true)
  }, [])

  const liveCallContact = useMemo(() => {
    if (!selected) return null
    const lead = leadDetail || {}
    return {
      user_id: selected.user_id,
      account_id: selected.slot,
      name: lead.name || selectedConv?.name || '',
      username: lead.username || selectedConv?.username || '',
      phone: lead.phone || '',
    }
  }, [selected, leadDetail, selectedConv])

  const openCallNowModal = useCallback(() => {
    unlockNotificationSound()
    setError('')
    setCallNowOpen(true)
  }, [])

  useEffect(() => {
    if (!toast) return undefined
    const id = window.setTimeout(() => setToast(null), 3200)
    return () => clearTimeout(id)
  }, [toast])

  async function handleLiveCallSelect(option) {
    if (!selected || !option?.can_open || !option.url) return
    setCallNowOpen(false)
    setToast(`Calling via ${callChannelLabel(option.id)}…`)
    window.open(option.url, '_blank', 'noopener,noreferrer')

    const optimisticInitiated = {
      id: `sys-live-${Date.now()}`,
      direction: 'system',
      text: buildLiveCallInitiatedMessage({ call_type: option.id }),
      timestamp: new Date().toISOString(),
    }
    setMessages(prev => [...prev, optimisticInitiated])
    stickToBottomRef.current = true
    forceScrollRef.current = true

    setCallNowLoading(true)
    try {
      const data = await initiateLiveCall(selected.slot, selected.user_id, option.id)
      onCrmUpdate?.(data.crm, data.lead, data.attempt)
      if (data.message) {
        setMessages(prev => appendMessageDeduped(prev, data.message))
      }
    } catch (e) {
      setError(String(e.message || e))
    } finally {
      setCallNowLoading(false)
    }
  }

  async function handleScheduleCallConfirm(body) {
    if (!selected) return
    setCallScheduling(true)
    try {
      const data = await scheduleCall(selected.slot, selected.user_id, body)
      onCrmUpdate?.(data.crm, data.lead, data.call)
      if (data.call) {
        const sysMsg = {
          id: `sys-call-${data.call.id || Date.now()}`,
          direction: 'system',
          text: buildCallSystemMessage(data.call),
          timestamp: new Date().toISOString(),
        }
        setMessages(prev => [...prev, sysMsg])
        stickToBottomRef.current = true
        forceScrollRef.current = true
      }
      setScheduleModalOpen(false)
    } catch (e) {
      setError(String(e.message || e))
    } finally {
      setCallScheduling(false)
    }
  }

  async function handleCallOutcome(status) {
    if (!outcomeCall) return
    setOutcomeSaving(true)
    try {
      const data = await completeCall(
        outcomeCall.account_id,
        outcomeCall.user_id,
        status,
      )
      onCrmUpdate?.(data.crm, data.lead, data.call)
      if (outcomeCall.id) skippedOutcomeIdsRef.current.add(outcomeCall.id)
      setOutcomeCall(null)
    } catch (e) {
      setError(String(e.message || e))
    } finally {
      setOutcomeSaving(false)
    }
  }

  function handleDismissOutcome() {
    if (outcomeCall?.id) skippedOutcomeIdsRef.current.add(outcomeCall.id)
    setOutcomeCall(null)
  }

  function handleStartCall(call) {
    const link = buildCallLink(call)
    if (link.url) window.open(link.url, '_blank', 'noopener,noreferrer')
    else setError(link.label)
  }

  function handleOpenReminderCall(reminder) {
    const conv = conversations.find(
      c => c.account_id === reminder.account_id
        && Number(c.user_id) === Number(reminder.user_id),
    )
    if (conv) selectConversation(conv)
  }

  async function handleFollowUp(hours) {
    if (!selected) return
    setFollowUpLoading(true)
    try {
      const data = await scheduleFollowUp(selected.slot, selected.user_id, hours)
      onCrmUpdate?.(data.crm, data.lead)
    } catch (e) {
      setError(String(e.message || e))
    } finally {
      setFollowUpLoading(false)
    }
  }

  const dueCount = crmState?.due_reminders?.length ?? 0
  const urgentBanner = formatUrgentTopBanner(alertCounts)

  return (
    <div className="inbox-root crm-root">
      <header className="inbox-toolbar crm-toolbar">
        <div className="inbox-toolbar-title">
          <h2>CRM Inbox</h2>
          <span className="inbox-toolbar-sub">Lead management · private DMs · multi-account</span>
        </div>
        <div className="inbox-toolbar-modes">
          <button
            type="button"
            className={`chip${mode === 'combined' ? ' chip--active' : ''}`}
            onClick={() => setMode('combined')}
          >
            Combined
          </button>
          <button
            type="button"
            className={`chip${mode === 'per_account' ? ' chip--active' : ''}`}
            onClick={() => setMode('per_account')}
          >
            Per account
          </button>
          {mode === 'per_account' && (
            <select
              className="input input--select inbox-slot-select"
              value={filterSlot}
              onChange={e => setFilterSlot(e.target.value)}
            >
              {accountSlots.map(s => (
                <option key={s} value={s}>{accountLabel(s)}</option>
              ))}
            </select>
          )}
        </div>
      </header>

      {urgentBanner && (
        <div className="crm-urgent-top-banner" role="alert">
          {urgentBanner}
        </div>
      )}

      <div className="crm-inbox-toolbar">
        <CrmStatsBar stats={crmState?.stats} dueCount={dueCount} alertCounts={alertCounts} />
        <CrmBuzzerToggle />
      </div>

      {toast && (
        <div className="crm-toast" role="status" aria-live="polite">
          {toast}
        </div>
      )}

      <CallReminderBanner
        reminders={crmState?.call_reminders}
        onOpen={handleOpenReminderCall}
      />

      <div className="crm-layout inbox-layout">
        <CRMInboxList
          conversations={conversations}
          selected={selected}
          mode={mode}
          filter={crmFilter}
          search={search}
          alertCounts={alertCounts}
          onFilterChange={setCrmFilter}
          onSearchChange={setSearch}
          onSelect={selectConversation}
        />
        <ChatWindow
          selected={selected}
          selectedConv={selectedConv}
          messages={messages}
          loadingMessages={loadingMessages}
          replyText={replyText}
          onReplyChange={setReplyText}
          onSend={sendReply}
          sending={sending}
          error={error}
          showNewMessages={showNewMessages}
          onJumpToLatest={jumpToLatest}
          onJumpToInbound={jumpToInbound}
          messagesScrollRef={messagesScrollRef}
          onMessagesScroll={handleMessagesScroll}
          messagesEndRef={messagesEndRef}
          onQuickReply={text => setReplyText(text)}
          onScheduleCall={openScheduleCallModal}
          onCallNow={openCallNowModal}
          onMarkSpam={handleMarkSpam}
          onMarkHandled={handleMarkHandled}
          crmSaving={crmSaving}
          scheduledCall={selectedCall}
        />
        <LeadDetailsPanel
          selected={selected}
          selectedConv={selectedConv}
          scheduledCall={selectedCall}
          onScheduleCall={openScheduleCallModal}
          onStartCall={handleStartCall}
          onCallNow={openCallNowModal}
          onUnblock={handleUnblock}
          lead={leadDetail || (selectedConv ? {
            status: selectedConv.crm_status,
            crm_blocked: selectedConv.crm_blocked,
            notes: selectedConv.crm_notes,
            first_message_at: selectedConv.crm_first_message_at,
            last_reply_at: selectedConv.crm_last_reply_at,
            last_contact_time: selectedConv.crm_last_contact_time,
            reminder_timestamp: selectedConv.crm_reminder_timestamp,
            name: selectedConv.name,
            username: selectedConv.username,
            scheduled_call: selectedConv.crm_scheduled_call,
          } : null)}
          onStatusChange={handleStatusChange}
          notes={notes}
          onNotesChange={setNotes}
          onSaveNotes={handleSaveNotes}
          onFollowUp2h={() => handleFollowUp(2)}
          onFollowUpTomorrow={() => handleFollowUp(24)}
          saving={crmSaving}
          followUpLoading={followUpLoading}
        />
      </div>

      <CallNowModal
        open={callNowOpen}
        contact={liveCallContact}
        leadName={selectedConv?.name || selectedConv?.username}
        onSelect={handleLiveCallSelect}
        onClose={() => setCallNowOpen(false)}
        loading={callNowLoading}
      />

      <ScheduleCallModal
        open={scheduleModalOpen}
        leadName={selectedConv?.name || selectedConv?.username}
        onConfirm={handleScheduleCallConfirm}
        onClose={() => setScheduleModalOpen(false)}
        saving={callScheduling}
      />

      <CallOutcomeModal
        open={Boolean(outcomeCall)}
        leadName={outcomeCall?.name || outcomeCall?.username}
        onSelect={handleCallOutcome}
        onDismiss={handleDismissOutcome}
        saving={outcomeSaving}
      />
    </div>
  )
}
