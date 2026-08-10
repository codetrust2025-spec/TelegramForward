/**
 * When a candidate mailbox needs the operator to reconnect Gmail.
 *
 * Extracted verbatim from RecruitmentMailPanelRedesign so the page badge and
 * the global fault alert cannot drift apart: one predicate, two callers. The
 * condition itself is unchanged.
 */
export function needsReconnect(mailbox) {
  const error = String(mailbox?.last_error_message || '').toLowerCase()
  return (
    mailbox?.connection_status === 'ERROR'
    || error.includes('expired')
    || error.includes('revoked')
  )
}
