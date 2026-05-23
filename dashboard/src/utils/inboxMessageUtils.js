export function formatInboxTime(iso) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return ''
    const now = new Date()
    const sameDay = d.toDateString() === now.toDateString()
    if (sameDay) {
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
    return d.toLocaleDateString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}

export function slotTag(slot) {
  const m = String(slot).match(/^account(\d+)$/i)
  return m ? `A${m[1]}` : slot
}

export function sameUser(a, b) {
  return Number(a) === Number(b)
}

export const LIVE_EVENTS = new Set([
  'new_message',
  'outgoing_message',
  'reply_sent',
  'message_read',
  'message_status',
])

const OUTBOUND_RANK = { failed: 0, sending: 1, sent: 2, delivered: 3, read: 4 }

export function outboundRank(status) {
  return OUTBOUND_RANK[status] ?? 2
}

export function defaultOutboundStatus(status) {
  if (status === 'sent') return 'delivered'
  return status || 'delivered'
}

export function appendMessageDeduped(prev, message) {
  if (!message) return prev
  if (prev.some(m => m.id === message.id)) return prev
  return [...prev, message]
}

export function mergeMessageLists(loaded, pending) {
  const byId = new Map()
  for (const m of loaded || []) byId.set(m.id, m)
  for (const m of pending || []) {
    if (!byId.has(m.id)) byId.set(m.id, m)
  }
  return [...byId.values()].sort((a, b) => (a.timestamp || '').localeCompare(b.timestamp || ''))
}

export function applyReadUpTo(messages, maxId) {
  if (!maxId) return messages
  const mid = Number(maxId)
  return messages.map(m => (
    m.direction === 'out' && Number(m.id) > 0 && Number(m.id) <= mid
      ? { ...m, status: 'read', read_at: m.read_at || new Date().toISOString() }
      : m
  ))
}

export function applyMessageStatus(messages, patch) {
  if (!patch) return messages
  const msgId = patch.message_id ?? patch.id
  const nextStatus = patch.status
  if (!nextStatus) return messages
  const uid = patch.user_id
  const rank = outboundRank(nextStatus)
  if (nextStatus === 'failed' && msgId == null) {
    return messages.map(m => (
      m.direction === 'out' && String(m.id).startsWith('pending-') && m.status === 'sending'
        ? { ...m, status: 'failed' }
        : m
    ))
  }
  return messages.map(m => {
    if (m.direction !== 'out') return m
    if (uid != null && m.chat_id != null && Number(m.chat_id) !== Number(uid)) return m
    const matchId = msgId != null && Number(m.id) === Number(msgId)
    const matchFailed = nextStatus === 'failed' && String(m.id).startsWith('pending-')
    if (!matchId && !matchFailed) return m
    if (outboundRank(m.status) >= rank && nextStatus !== 'failed') return m
    return {
      ...m,
      status: nextStatus,
      read_at: patch.read_at ?? m.read_at,
      id: matchId ? Number(msgId) : m.id,
      chat_id: patch.chat_id ?? m.chat_id ?? uid,
      account_id: patch.account_id ?? m.account_id,
    }
  })
}

export function markOutboundReadInThread(messages) {
  const now = new Date().toISOString()
  return messages.map(m => (
    m.direction === 'out' && m.status !== 'failed'
      ? { ...m, status: 'read', read_at: m.read_at || now }
      : m
  ))
}

export function replacePendingMessage(prev, pendingId, realMessage) {
  const without = prev.filter(m => m.id !== pendingId)
  return appendMessageDeduped(without, realMessage)
}

/** Remove only the oldest in-flight pending outbound (FIFO), not all with the same text. */
export function removeFirstMatchingPending(prev, text) {
  if (!text) return prev
  let removed = false
  return prev.filter(m => {
    if (removed) return true
    if (
      String(m.id).startsWith('pending-')
      && m.status === 'sending'
      && m.text === text
    ) {
      removed = true
      return false
    }
    return true
  })
}

/** Apply a live outbound/reply_sent row: drop one matching pending, then dedupe-append. */
export function applyOutboundLiveMessage(prev, message) {
  if (!message) return prev
  let base = prev
  if (message.direction === 'out') {
    base = removeFirstMatchingPending(prev, message.text)
  }
  let next = appendMessageDeduped(base, message)
  if (message.direction === 'in') next = markOutboundReadInThread(next)
  return next
}

export const SCROLL_NEAR_BOTTOM_PX = 100

export function isUserNearBottom(el, threshold = SCROLL_NEAR_BOTTOM_PX) {
  if (!el) return false
  return el.scrollHeight - el.scrollTop - el.clientHeight <= threshold
}

export function lastInboundMessage(messages) {
  const list = messages || []
  for (let i = list.length - 1; i >= 0; i -= 1) {
    if (list[i]?.direction === 'in') return list[i]
  }
  return null
}

export function countInbound(messages) {
  return (messages || []).filter(m => m?.direction === 'in').length
}
