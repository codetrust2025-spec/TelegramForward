import { API } from '../config.js'

export async function fetchWhatsAppStatus() {
  const res = await fetch(`${API}/whatsapp/status`, {
    cache: 'no-store',
    credentials: 'include',
  })
  const data = await res.json()
  if (data.status !== 'ok') {
    throw new Error(data.message || 'WhatsApp status failed')
  }
  return data
}

export async function linkLeadPhone(slot, userId, phone) {
  const res = await fetch(
    `${API}/crm/leads/${encodeURIComponent(slot)}/${userId}/link-phone`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ phone }),
    },
  )
  const data = await res.json()
  if (data.status !== 'ok') {
    throw new Error(data.message || 'Link phone failed')
  }
  return data
}

export async function sendWhatsAppTemplate(slot, userId, template, params = []) {
  const res = await fetch(`${API}/whatsapp/send-template`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({
      slot,
      user_id: Number(userId),
      template,
      params,
    }),
  })
  const data = await res.json()
  if (data.status !== 'ok') {
    throw new Error(data.message || data.error || 'Template send failed')
  }
  return data
}

export function formatPhoneDisplay(e164) {
  const digits = String(e164 || '').replace(/\D/g, '')
  if (digits.length === 12 && digits.startsWith('91')) {
    return `+91 ${digits.slice(2, 7)} ${digits.slice(7)}`
  }
  return e164 || ''
}
