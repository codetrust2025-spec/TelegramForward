import { API } from '../config.js'

export async function deleteInboxMessage({ slot, userId, messageId }) {
  const res = await fetch(`${API}/inbox/${encodeURIComponent(slot)}/${userId}/messages/${messageId}`, {
    method: 'DELETE',
    credentials: 'include',
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.message || data.detail || 'Delete failed')
  return data
}

export async function patchInboxMessage({ slot, userId, messageId, text }) {
  const res = await fetch(`${API}/inbox/${encodeURIComponent(slot)}/${userId}/messages/${messageId}`, {
    method: 'PATCH',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.message || data.detail || 'Edit failed')
  return data
}
