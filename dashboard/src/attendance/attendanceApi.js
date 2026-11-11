/** Attendance HTTP calls and the device metadata sent with a start. */

import { API } from '../config.js'

async function call(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) {
    const error = new Error(body.detail || 'Request failed')
    error.status = response.status
    error.detail = body.detail
    throw error
  }
  return body
}

/**
 * What the browser can say about itself.
 *
 * This is a hint about which machine was used and nothing more — every field
 * here is written by the page, so none of it is evidence of location. Whether
 * the request came from the office is decided server-side from the IP.
 */
export function deviceInfo() {
  if (typeof navigator === 'undefined') return {}
  const screen = typeof window !== 'undefined' && window.screen
  return {
    user_agent: navigator.userAgent || '',
    platform: navigator.platform || '',
    language: navigator.language || '',
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || '',
    screen: screen ? `${screen.width}x${screen.height}` : '',
  }
}

export const fetchToday = () => call('/api/attendance/today')

export const startWork = () =>
  call('/api/attendance/start', {
    method: 'POST',
    body: JSON.stringify({ device: deviceInfo() }),
  })

export const fetchSummary = (month) =>
  call(`/api/attendance/summary?month=${encodeURIComponent(month)}`)

export const fetchRecords = (month, employeeId = null) =>
  call(
    `/api/attendance/records?month=${encodeURIComponent(month)}`
    + (employeeId ? `&employee_id=${encodeURIComponent(employeeId)}` : ''),
  )

export const fetchConfig = () => call('/api/attendance/config')

export const saveConfig = (patch) =>
  call('/api/attendance/config', { method: 'PUT', body: JSON.stringify(patch) })

export const fetchEmployees = () => call('/api/attendance/employees')

export const assignEmployee = (payload) =>
  call('/api/attendance/employees', { method: 'POST', body: JSON.stringify(payload) })

export const overrideDay = (payload) =>
  call('/api/attendance/override', { method: 'POST', body: JSON.stringify(payload) })
