/**
 * The app-global notification sound manager.
 *
 * Mounted once, above the view switch, for the whole authenticated session. It
 * owns every subscription that can make a noise, so what the user is currently
 * looking at has no bearing on what they hear. Before this existed, a delayed
 * CRM reply was silent unless the Inbox happened to be open, a selection mail
 * was silent unless the notifications page was open, and an expired Gmail token
 * was silent unless the recruitment page was open.
 *
 * It renders nothing. Page components still render their own UI from their own
 * data; they simply no longer own the sound lifecycle.
 */

import { useEffect, useRef } from 'react'
import { API } from '../config.js'
import { useAuth } from '../context/AuthContext.jsx'
import { needsReconnect } from '../utils/mailboxStatus.js'
import { REPLY_CHECK_INTERVAL_MS } from '../utils/replyAlert.js'
import { subscribeMailEvents } from './mailEventStream.js'
import {
  notifyCallReminder,
  notifyGmailReconnect,
  notifyTrackedMail,
  stopUnreadAmbience,
  syncUnreadAmbience,
} from './notificationEvents.js'
import { resetReplyAlertSounds, syncReplyAlertSounds } from './replyAlertSounds.js'
import { useInterviewReminders } from './useInterviewReminders.js'
import { installSoundPreview } from './soundPreview.js'

const GMAIL_HEALTH_POLL_MS = 120000
const AMBIENCE_RECHECK_MS = 60000

/** True only in a dev server build; bundlers drop the preview from production. */
function isDevBuild() {
  try {
    return Boolean(import.meta.env?.DEV)
  } catch {
    return false
  }
}

export function GlobalNotificationSounds({
  inboxState = null,
  inboxUnreadTotal = 0,
  crmState = null,
}) {
  const { authenticated } = useAuth()

  // Console-only harness for auditioning the ten sounds. Dev builds only.
  useEffect(() => {
    if (isDevBuild()) installSoundPreview()
  }, [])

  // Interview reminders keep their own 5-minute poll and notification windows;
  // they simply live here now instead of on a page provider.
  useInterviewReminders(authenticated)

  /* Tracked recruitment mail — selections and interview bookings. */
  useEffect(() => {
    if (!authenticated) return undefined
    return subscribeMailEvents((payload, meta) => {
      // Events mirrored from another tab update UI there but must not sound
      // twice; only what this tab received from the server is audible.
      if (!meta?.fromSocket) return
      notifyTrackedMail(payload)
    })
  }, [authenticated])

  /* Gmail credential faults — polled, because there is no push for them. */
  const gmailEnabledRef = useRef(null)
  useEffect(() => {
    if (!authenticated) return undefined
    let cancelled = false
    let timer = null

    const readMailboxes = async () => {
      try {
        if (gmailEnabledRef.current == null) {
          const config = await fetch(`${API}/api/ai-recruitment/config`, { credentials: 'include' })
            .then((r) => (r.ok ? r.json() : null))
            .catch(() => null)
          gmailEnabledRef.current = Boolean(config?.enabled)
        }
        if (!gmailEnabledRef.current || cancelled) return

        const body = await fetch(`${API}/api/candidate-mailboxes/health?_=${Date.now()}`, {
          credentials: 'include',
        })
          .then((r) => (r.ok ? r.json() : null))
          .catch(() => null)
        if (!body || cancelled) return

        const disconnected = (body.mailboxes || [])
          .filter((mailbox) => needsReconnect(mailbox))
          .map((mailbox) => ({
            id: mailbox.id,
            name: mailbox.candidate_name || mailbox.name || '',
          }))
        notifyGmailReconnect(disconnected)
      } catch {
        /* a health blip must not break the session */
      }
    }

    readMailboxes()
    timer = window.setInterval(readMailboxes, GMAIL_HEALTH_POLL_MS)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [authenticated])

  /* CRM reply SLA tiers — driven by inbox state held at app level.
   *
   * The tiers are elapsed-time thresholds, so they have to be re-evaluated on a
   * clock as well as on new inbox frames. InboxPanel used to drive that with a
   * REPLY_CHECK_INTERVAL_MS tick of its own; the same cadence now runs here, so
   * a conversation crosses 10 or 20 minutes audibly whatever page is open. */
  useEffect(() => {
    if (!authenticated) return undefined
    const resync = () => syncReplyAlertSounds(inboxState)
    resync()
    const tick = window.setInterval(resync, REPLY_CHECK_INTERVAL_MS)
    window.addEventListener('crm-buzzer-toggle', resync)
    window.addEventListener('sound-quiet-hours-change', resync)
    return () => {
      window.clearInterval(tick)
      window.removeEventListener('crm-buzzer-toggle', resync)
      window.removeEventListener('sound-quiet-hours-change', resync)
    }
  }, [authenticated, inboxState])

  /* Unread inbox ambience — 60s re-check preserved from App. */
  useEffect(() => {
    if (!authenticated) return undefined
    const resync = () => syncUnreadAmbience(inboxUnreadTotal, inboxState)
    resync()
    const tick = window.setInterval(resync, AMBIENCE_RECHECK_MS)
    window.addEventListener('sound-quiet-hours-change', resync)
    window.addEventListener('crm-buzzer-toggle', resync)
    return () => {
      window.clearInterval(tick)
      window.removeEventListener('sound-quiet-hours-change', resync)
      window.removeEventListener('crm-buzzer-toggle', resync)
    }
  }, [authenticated, inboxUnreadTotal, inboxState])

  /* Scheduled calls falling due — same ring as an incoming call, by design. */
  useEffect(() => {
    if (!authenticated) return undefined
    for (const reminder of crmState?.call_reminders || []) {
      notifyCallReminder(reminder.id || `${reminder.account_id}:${reminder.user_id}`)
    }
    return undefined
  }, [authenticated, crmState?.call_reminders])

  /* Everything stops when the session does. */
  useEffect(() => {
    if (authenticated) return undefined
    stopUnreadAmbience()
    resetReplyAlertSounds()
    return undefined
  }, [authenticated])

  useEffect(
    () => () => {
      stopUnreadAmbience()
      resetReplyAlertSounds()
    },
    [],
  )

  return null
}

export default GlobalNotificationSounds
