const KEY = 'ta_inbox_pins_v1'

function load() {
  try {
    const raw = localStorage.getItem(KEY)
    const data = raw ? JSON.parse(raw) : {}
    return data && typeof data === 'object' ? data : {}
  } catch {
    return {}
  }
}

function save(data) {
  try {
    localStorage.setItem(KEY, JSON.stringify(data))
  } catch {
    /* ignore quota */
  }
}

function convKey(slot, userId) {
  return `${slot}:${userId}`
}

export function isMessagePinned(slot, userId, messageId) {
  const store = load()
  const set = store[convKey(slot, userId)]
  return Array.isArray(set) && set.includes(String(messageId))
}

export function toggleMessagePin(slot, userId, messageId) {
  const store = load()
  const key = convKey(slot, userId)
  const id = String(messageId)
  const prev = new Set(Array.isArray(store[key]) ? store[key].map(String) : [])
  if (prev.has(id)) prev.delete(id)
  else prev.add(id)
  store[key] = [...prev]
  save(store)
  return prev.has(id)
}
