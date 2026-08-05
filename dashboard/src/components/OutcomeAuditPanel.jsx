import React, { useCallback, useEffect, useMemo, useState } from "react";
import { API } from "../config.js";
import { useConfirm } from "../context/ConfirmContext.jsx";
import { MailMonitoringTabs } from "./MailMonitoringTabs.jsx";
import { useDialogA11y } from "../hooks/useDialogA11y.js";
import { ButtonContent, InlineLoader } from "../Loader.jsx";

const request = async (path, options = {}) => {
  const response = await fetch(`${API}${path}`, {
    credentials: "include",
    cache: !options.method || options.method === "GET" ? "no-store" : undefined,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok)
    throw new Error(body.detail || body.message || "Request failed");
  return body;
};

export const SELECTION = "SELECTION";
export const INTERVIEW = "INTERVIEW";

/**
 * Selection results and interview-slot results answer different questions and
 * are never totalled together. Each mode owns its own categories; the two
 * lists below share no entry, which is what stops a mailbox full of interview
 * invitations from reading as hiring progress.
 */
const SELECTION_OUTCOMES = [
  ["VERIFIED_OFFER_LETTER", "Verified offer letter"],
  ["FINAL_SELECTION", "Final selection"],
  ["OFFER_INDICATION", "Offer indication"],
  ["JOINING_CONFIRMED", "Joining confirmation"],
  ["BACKGROUND_VERIFICATION", "Background verification"],
  ["SHORTLISTED", "Shortlisted"],
  ["NEXT_ROUND", "Next round"],
  ["REJECTED", "Rejected"],
  ["MANUAL_REVIEW_REQUIRED", "Manual review required"],
  ["NOT_RELEVANT", "No selection evidence"],
];

const INTERVIEW_OUTCOMES = [
  ["INTERVIEW_INVITE", "Interview invitation"],
  ["INTERVIEW_AUTO_BOOKED", "Interview automatically booked"],
  ["INTERVIEW_RESCHEDULED", "Interview rescheduled"],
  ["INTERVIEW_CANCELLED", "Interview cancelled"],
  ["BOOKING_BLOCKED", "Booking blocked"],
  ["DUPLICATE_BOOKING_IGNORED", "Duplicate booking ignored"],
  ["SLOT_CONFLICT", "Slot conflict"],
  ["MISSING_DATE_OR_TIME", "Missing date or time"],
  ["MISSED_OR_UNPROCESSED_INVITE", "Missed or unprocessed invite"],
  ["HISTORICAL_NOT_BOOKED", "Historical, not booked"],
  ["NOT_RELEVANT", "No interview activity"],
];

const SELECTION_TILES = [
  ["candidates_verified_offer_letters", "Verified offer letters"],
  ["candidates_final_selection", "Final selections"],
  ["candidates_offer_indication", "Offer indications"],
  ["candidates_joining_confirmed", "Joining confirmed"],
  ["candidates_background_verification", "Background verification"],
  ["candidates_shortlisted", "Shortlisted"],
  ["candidates_next_round", "Next round"],
  ["candidates_rejected", "Rejected"],
  ["candidates_manual_review_outcome", "Manual review required"],
  ["candidates_no_outcome", "No selection evidence"],
];

const INTERVIEW_TILES = [
  ["candidates_with_interview_invites", "Interview invitations"],
  ["candidates_auto_booked", "Automatically booked"],
  ["candidates_interview_rescheduled", "Rescheduled"],
  ["candidates_interview_cancelled", "Cancelled"],
  ["candidates_booking_blocked", "Booking blocked"],
  ["candidates_duplicate_booking_ignored", "Duplicate ignored"],
  ["candidates_slot_conflict", "Slot conflicts"],
  ["candidates_missing_date_or_time", "Missing date or time"],
  ["candidates_missed_invites", "Missed or unprocessed invites"],
  ["candidates_historical_not_booked", "Historical, not booked"],
];

const SHARED_TILES = [
  ["total_connected_mailboxes", "Connected mailboxes"],
  ["mailboxes_scanned", "Scanned"],
  ["mailboxes_failed", "Failed to scan"],
  ["pipeline_gaps_total", "Pipeline gaps"],
];

const CLEANUP_REASONS = {
  IRRELEVANT: "Irrelevant",
  DUPLICATE: "Duplicate",
  SUPERSEDED: "Superseded",
  WRONG_AUDIT_MODE: "Moved to Interview Slot Audit",
};

// Approval is offered per application, never per loose message: it requires a
// named company and role, an authentic company sender, strong evidence and no
// later conflicting message. The server enforces the same gate.

const AUTHENTICITY = ["PASS", "PARTIAL", "UNVERIFIED", "SUSPICIOUS"];

const LABELS = new Map([...SELECTION_OUTCOMES, ...INTERVIEW_OUTCOMES]);

const human = (value) =>
  LABELS.get(value) ||
  String(value || "")
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/^\w/, (c) => c.toUpperCase());

const when = (value) => {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? String(value)
    : date.toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
};

const day = (value) => {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? String(value)
    : date.toLocaleDateString("en-IN", { dateStyle: "medium" });
};

export function OutcomeAuditPanel() {
  const { confirm } = useConfirm();
  const [mode, setMode] = useState(SELECTION);
  const [view, setView] = useState("report");
  const [summary, setSummary] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [gaps, setGaps] = useState([]);
  const [excluded, setExcluded] = useState([]);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const [filters, setFilters] = useState({
    candidate: "",
    company: "",
    outcome: "ALL",
    authenticity: "ALL",
    sync_status: "ALL",
    min_confidence: "",
    manual_review: false,
    mismatch: false,
  });
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const isSelection = mode === SELECTION;
  const outcomeOptions = isSelection ? SELECTION_OUTCOMES : INTERVIEW_OUTCOMES;
  const modeTiles = isSelection ? SELECTION_TILES : INTERVIEW_TILES;

  const query = useMemo(() => {
    const params = new URLSearchParams();
    params.set("mode", mode);
    if (filters.candidate.trim()) params.set("candidate", filters.candidate.trim());
    if (filters.company.trim()) params.set("company", filters.company.trim());
    if (filters.outcome !== "ALL") params.set("outcome", filters.outcome);
    if (filters.authenticity !== "ALL") params.set("authenticity", filters.authenticity);
    if (filters.sync_status !== "ALL") params.set("sync_status", filters.sync_status);
    if (filters.min_confidence) params.set("min_confidence", filters.min_confidence);
    if (filters.manual_review) params.set("manual_review", "1");
    if (isSelection && filters.mismatch) params.set("mismatch", "1");
    return params.toString();
  }, [filters, mode, isSelection]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [summaryBody, candidateBody, gapBody, excludedBody] = await Promise.all([
        request(`/api/mail-outcome-audit/summary?${query}`),
        request(`/api/mail-outcome-audit/candidates?${query}`),
        request(`/api/mail-outcome-audit/gaps?mode=${mode}&limit=300`),
        request(`/api/mail-outcome-audit/excluded?limit=500`),
      ]);
      setSummary(summaryBody.summary || null);
      setCandidates(candidateBody.candidates || []);
      setGaps(gapBody.gaps || []);
      setExcluded(excludedBody.excluded || []);
    } catch (exc) {
      setError(exc.message || "Could not load the audit report");
    } finally {
      setLoading(false);
    }
  }, [query, mode]);

  useEffect(() => {
    load();
  }, [load]);

  // An outcome filter from one mode means nothing in the other.
  const switchMode = useCallback((next) => {
    setMode(next);
    setView("report");
    setDetail(null);
    setFilters((prev) => ({ ...prev, outcome: "ALL", mismatch: false }));
  }, []);

  const runAudit = useCallback(async () => {
    const ok = await confirm({
      title: "Run the mail outcome audit",
      message:
        "This reads every authorized candidate mailbox and rebuilds both audits. " +
        "It is report-only: no email is modified and no candidate status changes.",
      confirmLabel: "Run audit",
    });
    if (!ok) return;
    setRunning(true);
    setError("");
    setNotice("");
    try {
      const body = await request("/api/mail-outcome-audit/run", {
        method: "POST",
        body: JSON.stringify({ incremental: false }),
      });
      const run = body.run || {};
      setNotice(
        `Audit complete — ${run.mailboxes_scanned}/${run.mailboxes_total} mailboxes scanned, ` +
          `${run.messages_examined} messages examined, ${run.gaps_written} pipeline gaps recorded.` +
          (run.mailboxes_failed ? ` ${run.mailboxes_failed} mailbox(es) could not be scanned.` : ""),
      );
      await load();
    } catch (exc) {
      setError(exc.message || "The audit could not be started");
    } finally {
      setRunning(false);
    }
  }, [confirm, load]);

  const exportReport = useCallback(() => {
    // The export carries exactly the rows on screen, mode included.
    window.open(`${API}/api/mail-outcome-audit/export?${query}`, "_blank", "noopener");
  }, [query]);

  const openCandidate = useCallback(
    async (row) => {
      setDetail({ loading: true, candidate: row });
      try {
        const params = new URLSearchParams();
        params.set("mode", mode);
        if (dateFrom) params.set("date_from", dateFrom);
        if (dateTo) params.set("date_to", dateTo);
        const body = await request(
          `/api/mail-outcome-audit/candidates/${encodeURIComponent(row.canonical_candidate_id)}?${params}`,
        );
        setDetail({ loading: false, ...body });
      } catch (exc) {
        setDetail({ loading: false, candidate: row, error: exc.message });
      }
    },
    [dateFrom, dateTo, mode],
  );

  const approve = useCallback(
    async (finding, decision) => {
      const ok = await confirm({
        title: decision === "APPROVED" ? "Apply this outcome" : "Dismiss this outcome",
        message:
          decision === "APPROVED"
            ? `Set this candidate's status from the audited outcome "${human(finding.outcome)}"? ` +
              "This is the only action that changes a candidate record."
            : "Record that this audited outcome was reviewed and not applied?",
        confirmLabel: decision === "APPROVED" ? "Apply status" : "Dismiss",
      });
      if (!ok) return;
      try {
        const body = await request(
          `/api/mail-outcome-audit/findings/${encodeURIComponent(finding.id)}/approve`,
          { method: "POST", body: JSON.stringify({ decision }) },
        );
        const approval = body.approval || {};
        setNotice(
          decision === "APPROVED"
            ? `Status set to "${approval.status}" for candidate ${approval.candidate_id}.`
            : "Outcome recorded as reviewed; nothing was changed.",
        );
        await load();
        if (detail?.candidate) await openCandidate(detail.candidate);
      } catch (exc) {
        setError(exc.message || "The approval could not be applied");
      }
    },
    [confirm, load, detail, openCandidate],
  );

  const setFilter = (key, value) => setFilters((prev) => ({ ...prev, [key]: value }));

  const closeDetail = useCallback(() => setDetail(null), []);
  const dialogRef = useDialogA11y(Boolean(detail), closeDetail);

  const tiles = [...modeTiles, ...SHARED_TILES];

  return (
    <div className="outcome-audit">
      <header className="outcome-audit__header">
        <div>
          <p className="outcome-audit__eyebrow">AI MAIL MONITORING</p>
          <h1>Candidate mail outcome audit</h1>
          <p className="outcome-audit__lede">
            Evidence-based reconstruction of what every connected mailbox actually received.
            Read-only: no email is sent, deleted, labelled or modified, and candidate status
            changes only through an explicit approval below.
          </p>
        </div>
        <div className="outcome-audit__actions">
          <button type="button" className="cand-btn cand-btn--primary" onClick={runAudit} disabled={running}>
            <ButtonContent loading={running} loadingLabel="Auditing…">
              Run full audit
            </ButtonContent>
          </button>
          <button type="button" className="cand-btn cand-btn--ghost" onClick={exportReport}>
            Export CSV
          </button>
          <button type="button" className="cand-btn cand-btn--ghost" onClick={load} disabled={loading}>
            Refresh
          </button>
        </div>
      </header>

      <MailMonitoringTabs active="outcome-audit" />

      <nav className="outcome-audit__modes" aria-label="Audit mode">
        <button
          type="button"
          className={mode === SELECTION && view === "report" ? "is-active" : ""}
          aria-current={mode === SELECTION && view === "report" ? "page" : undefined}
          onClick={() => switchMode(SELECTION)}
        >
          Selection Audit
        </button>
        <button
          type="button"
          className={mode === INTERVIEW && view === "report" ? "is-active" : ""}
          aria-current={mode === INTERVIEW && view === "report" ? "page" : undefined}
          onClick={() => switchMode(INTERVIEW)}
        >
          Interview Slot Audit
        </button>
        <button
          type="button"
          className={view === "gaps" ? "is-active" : ""}
          aria-current={view === "gaps" ? "page" : undefined}
          onClick={() => {
            setView("gaps");
            setDetail(null);
          }}
        >
          Pipeline Gaps ({gaps.length})
        </button>
        {isSelection && (
          <button
            type="button"
            className={view === "excluded" ? "is-active" : ""}
            aria-current={view === "excluded" ? "page" : undefined}
            onClick={() => {
              setView("excluded");
              setDetail(null);
            }}
            title="Findings cleaned out of the Selection Audit. Nothing is deleted."
          >
            Excluded ({excluded.length})
          </button>
        )}
      </nav>

      <p className="outcome-audit__runline">
        {view === "excluded"
          ? "Findings cleaned out of the Selection Audit. The email, its attachments and its " +
            "evidence are unchanged; only the counting excludes them."
          : view === "gaps"
          ? `Pipeline gaps affecting the ${isSelection ? "selection" : "interview slot"} audit. ` +
            "Mailbox-level sync failures appear in both."
          : isSelection
            ? "Offer, selection, joining, background verification, shortlist and rejection evidence only."
            : "Interview invitations, bookings, reschedules, cancellations and slot problems only."}
        {summary?.latest_run && (
          <>
            {" · "}Last run {when(summary.latest_run.started_at)} · {summary.latest_run.status} ·{" "}
            {summary.latest_run.mode === "REPORT_ONLY" ? "report only" : summary.latest_run.mode}
          </>
        )}
      </p>

      {error && <div className="outcome-audit__error">{error}</div>}
      {notice && <div className="outcome-audit__notice">{notice}</div>}

      {view === "report" && (
        <section className="outcome-audit__tiles" aria-label="Audit summary">
          {summary
            ? tiles.map(([key, label]) => (
                <div className="outcome-audit__tile" key={key}>
                  <span className="outcome-audit__tile-value">{summary[key] ?? 0}</span>
                  <span className="outcome-audit__tile-label">{label}</span>
                </div>
              ))
            : loading && <InlineLoader label="Loading summary…" />}
        </section>
      )}

      {view === "report" && (
        <section className="outcome-audit__filters" aria-label="Audit filters">
          <input
            className="cand-input"
            placeholder="Candidate name, id or Gmail"
            value={filters.candidate}
            onChange={(e) => setFilter("candidate", e.target.value)}
            aria-label="Filter by candidate"
          />
          <input
            className="cand-input"
            placeholder="Company"
            value={filters.company}
            onChange={(e) => setFilter("company", e.target.value)}
            aria-label="Filter by company"
          />
          <select
            className="cand-input"
            value={filters.outcome}
            onChange={(e) => setFilter("outcome", e.target.value)}
            aria-label="Filter by outcome"
          >
            <option value="ALL">All outcomes</option>
            {outcomeOptions.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <select
            className="cand-input"
            value={filters.authenticity}
            onChange={(e) => setFilter("authenticity", e.target.value)}
            aria-label="Filter by authenticity"
          >
            <option value="ALL">All authenticity</option>
            {AUTHENTICITY.map((value) => (
              <option key={value} value={value}>
                {human(value)}
              </option>
            ))}
          </select>
          <select
            className="cand-input"
            value={filters.sync_status}
            onChange={(e) => setFilter("sync_status", e.target.value)}
            aria-label="Filter by mailbox sync status"
          >
            <option value="ALL">All mailboxes</option>
            <option value="MONITORING_ACTIVE">Monitoring active</option>
            <option value="CONNECTED">Connected</option>
            <option value="FAILED">Sync failed</option>
          </select>
          <select
            className="cand-input"
            value={filters.min_confidence}
            onChange={(e) => setFilter("min_confidence", e.target.value)}
            aria-label="Filter by minimum confidence"
          >
            <option value="">Any confidence</option>
            <option value="60">60% and above</option>
            <option value="75">75% and above</option>
            <option value="85">85% and above</option>
          </select>
          <input
            type="date"
            className="cand-input"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            aria-label="Evidence from date"
          />
          <input
            type="date"
            className="cand-input"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            aria-label="Evidence to date"
          />
          <label className="cand-toggle">
            <input
              type="checkbox"
              checked={filters.manual_review}
              onChange={(e) => setFilter("manual_review", e.target.checked)}
            />
            <span>Manual review only</span>
          </label>
          {isSelection && (
            <label className="cand-toggle">
              <input
                type="checkbox"
                checked={filters.mismatch}
                onChange={(e) => setFilter("mismatch", e.target.checked)}
              />
              <span>Status mismatches only</span>
            </label>
          )}
        </section>
      )}

      {loading ? (
        <InlineLoader label="Loading audit results…" />
      ) : view === "report" ? (
        <div className="outcome-audit__table-wrap">
          <table className="outcome-audit__table">
            <thead>
              <tr>
                <th>Candidate</th>
                <th>Gmail</th>
                <th>Mailbox</th>
                <th>Strongest outcome</th>
                <th>Confidence</th>
                {isSelection && <th>Authenticity</th>}
                {isSelection ? <th>System status</th> : <th>Interview activity</th>}
                <th>Companies</th>
                <th>Last sync</th>
                <th aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {candidates.length === 0 ? (
                <tr>
                  <td colSpan={10} className="outcome-audit__empty">
                    No audited mailboxes match these filters.
                  </td>
                </tr>
              ) : (
                candidates.map((row) => (
                  <tr
                    key={row.canonical_candidate_id}
                    className={row.status_mismatch ? "is-mismatch" : ""}
                  >
                    <td>
                      <strong>{row.candidate_name || "Unnamed"}</strong>
                      <span className="outcome-audit__sub">ID: {row.canonical_candidate_id}</span>
                    </td>
                    <td>{row.email_address}</td>
                    <td>
                      <span className={`outcome-audit__pill outcome-audit__pill--${String(row.scan_status).toLowerCase()}`}>
                        {human(row.monitoring_status)}
                      </span>
                      {row.scan_status === "FAILED" && (
                        <span className="outcome-audit__sub">{row.scan_error}</span>
                      )}
                    </td>
                    <td>
                      <span className={`outcome-audit__outcome outcome-audit__outcome--${String(row.strongest_outcome).toLowerCase()}`}>
                        {human(row.strongest_outcome)}
                      </span>
                      {row.conflicting_evidence && (
                        <span className="outcome-audit__warn">Conflicting evidence</span>
                      )}
                      {row.suspicious_evidence && (
                        <span className="outcome-audit__warn">Authenticity concern</span>
                      )}
                    </td>
                    <td>{row.strongest_confidence ? `${Math.round(row.strongest_confidence)}%` : "—"}</td>
                    {isSelection && <td>{human(row.strongest_authenticity) || "—"}</td>}
                    {isSelection ? (
                      <td>
                        {row.system_status || "—"}
                        {row.status_mismatch && (
                          <span className="outcome-audit__warn" title={row.mismatch_detail}>
                            Mismatch
                          </span>
                        )}
                      </td>
                    ) : (
                      <td>
                        {Object.entries(row.outcome_counts || {}).length === 0
                          ? "—"
                          : Object.entries(row.outcome_counts || {})
                              .map(([key, count]) => `${human(key)} × ${count}`)
                              .join(", ")}
                      </td>
                    )}
                    <td>{(row.companies || []).join(", ") || "—"}</td>
                    <td>{when(row.last_successful_sync_at)}</td>
                    <td>
                      <button
                        type="button"
                        className="cand-btn cand-btn--ghost cand-btn--sm"
                        onClick={() => openCandidate(row)}
                      >
                        Evidence
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      ) : view === "excluded" ? (
        <div className="outcome-audit__table-wrap">
          <table className="outcome-audit__table">
            <thead>
              <tr>
                <th>Reason</th>
                <th>Candidate</th>
                <th>Classified as</th>
                <th>Subject</th>
                <th>Sender</th>
                <th>Received</th>
                <th>Why it was excluded</th>
                <th>Excluded at</th>
              </tr>
            </thead>
            <tbody>
              {excluded.length === 0 ? (
                <tr>
                  <td colSpan={8} className="outcome-audit__empty">
                    Nothing has been excluded from the Selection Audit.
                  </td>
                </tr>
              ) : (
                excluded.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <span className={`outcome-audit__sev outcome-audit__sev--${String(row.suppression_reason).toLowerCase()}`}>
                        {CLEANUP_REASONS[row.suppression_reason] || row.suppression_reason}
                      </span>
                    </td>
                    <td>
                      {row.candidate_name || row.canonical_candidate_id}
                      <span className="outcome-audit__sub">{row.email_address}</span>
                    </td>
                    <td>{human(row.outcome)}</td>
                    <td className="outcome-audit__detailcell">{row.subject || "(no subject)"}</td>
                    <td>{row.sender_email}</td>
                    <td>{day(row.received_at)}</td>
                    <td className="outcome-audit__detailcell">{row.suppression_detail}</td>
                    <td>{when(row.suppressed_at)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="outcome-audit__table-wrap">
          <table className="outcome-audit__table">
            <thead>
              <tr>
                <th>Severity</th>
                <th>Gap</th>
                <th>Candidate</th>
                <th>Detail</th>
                <th>Audit reads</th>
                <th>Pipeline recorded</th>
              </tr>
            </thead>
            <tbody>
              {gaps.length === 0 ? (
                <tr>
                  <td colSpan={6} className="outcome-audit__empty">
                    No pipeline gaps recorded for this audit.
                  </td>
                </tr>
              ) : (
                gaps.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <span className={`outcome-audit__sev outcome-audit__sev--${String(row.severity).toLowerCase()}`}>
                        {row.severity}
                      </span>
                    </td>
                    <td>{human(row.gap_type)}</td>
                    <td>
                      {row.candidate_name || row.canonical_candidate_id}
                      <span className="outcome-audit__sub">{row.email_address}</span>
                    </td>
                    <td className="outcome-audit__detailcell">{row.detail}</td>
                    <td>{row.audit_outcome ? human(row.audit_outcome) : "—"}</td>
                    <td>{row.pipeline_outcome ? human(row.pipeline_outcome) : "—"}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {detail && (
        <div
          className="outcome-audit__drawer-backdrop"
          role="presentation"
          onClick={closeDetail}
        >
          <aside
            ref={dialogRef}
            className="outcome-audit__drawer"
            role="dialog"
            aria-modal="true"
            aria-label="Candidate mail evidence"
            onClick={(e) => e.stopPropagation()}
          >
            <header>
              <div>
                <h2>{detail.candidate?.candidate_name || "Candidate"}</h2>
                <p>
                  ID {detail.candidate?.canonical_candidate_id} · {detail.candidate?.email_address}
                  {" · "}
                  {isSelection ? "Selection audit" : "Interview slot audit"}
                </p>
              </div>
              <button type="button" className="cand-btn cand-btn--ghost cand-btn--sm" onClick={closeDetail}>
                Close
              </button>
            </header>

            {detail.loading ? (
              <InlineLoader label="Loading evidence…" />
            ) : detail.error ? (
              <div className="outcome-audit__error">{detail.error}</div>
            ) : (
              <>
                <p className="outcome-audit__recommend">
                  <strong>Recommended action:</strong> {detail.candidate?.recommended_action}
                </p>
                {detail.candidate?.mismatch_detail && (
                  <p className="outcome-audit__warnbox">{detail.candidate.mismatch_detail}</p>
                )}

                {!isSelection && (detail.bookings || []).length > 0 && (
                  <>
                    <h3>Booking outcomes</h3>
                    <ul className="outcome-audit__gaplist">
                      {detail.bookings.map((booking) => (
                        <li key={booking.id}>
                          <strong>{human(booking.booking_outcome)}</strong> — {booking.booking_status}
                          {booking.failure_message ? ` · ${booking.failure_message}` : ""}
                          {booking.created_at ? ` · ${day(booking.created_at)}` : ""}
                        </li>
                      ))}
                    </ul>
                  </>
                )}

                {isSelection && (detail.applications || []).length > 0 && (
                  <>
                    <h3>By company and role</h3>
                    <p className="outcome-audit__sub">
                      Each application is its own lifecycle. A result from one company never
                      affects another.
                    </p>
                    <ol className="outcome-audit__applications">
                      {detail.applications.map((app) => (
                        <li key={app.application_key}>
                          <div className="outcome-audit__app-head">
                            <strong>{app.company}</strong>
                            <span className="outcome-audit__sub">{app.role}</span>
                          </div>
                          <div className="outcome-audit__app-state">
                            <span className={`outcome-audit__outcome outcome-audit__outcome--${String(app.latest_verified_state).toLowerCase()}`}>
                              {human(app.latest_verified_state)}
                            </span>
                            <span className={`outcome-audit__strength outcome-audit__strength--${String(app.evidence_strength).toLowerCase()}`}>
                              {human(app.evidence_strength)} evidence
                            </span>
                            <span>{Math.round(app.confidence || 0)}%</span>
                            <span>{human(app.authenticity)}</span>
                            <span>{human(app.source_type)}</span>
                            <span>{day(app.latest_message_at)}</span>
                          </div>
                          <ul className="outcome-audit__app-mails">
                            {(app.messages || []).map((mail) => (
                              <li key={mail.id}>
                                {day(mail.received_at)} · {human(mail.outcome)} ·{" "}
                                {mail.subject || "(no subject)"}
                                <span className="outcome-audit__sub">{mail.sender_email}</span>
                              </li>
                            ))}
                          </ul>
                          {app.approval?.eligible ? (
                            <div className="outcome-audit__approve">
                              <button
                                type="button"
                                className="cand-btn cand-btn--primary cand-btn--sm"
                                onClick={() =>
                                  approve({ id: app.strongest_finding_id,
                                            outcome: app.latest_verified_state }, "APPROVED")
                                }
                              >
                                Approve status update
                              </button>
                              <button
                                type="button"
                                className="cand-btn cand-btn--ghost cand-btn--sm"
                                onClick={() =>
                                  approve({ id: app.strongest_finding_id,
                                            outcome: app.latest_verified_state }, "REJECTED")
                                }
                              >
                                Reviewed, do not apply
                              </button>
                            </div>
                          ) : (
                            <p className="outcome-audit__blocked">
                              {app.approval?.message}
                              <span className="outcome-audit__sub">
                                {(app.approval?.blockers || []).join(" ")}
                              </span>
                            </p>
                          )}
                        </li>
                      ))}
                    </ol>
                  </>
                )}

                <h3>{isSelection ? "Selection evidence" : "Interview mail"}, oldest first</h3>
                {(detail.findings || []).filter((f) => f.outcome !== "NOT_RELEVANT").length === 0 ? (
                  <p className="outcome-audit__empty">
                    {isSelection
                      ? "No mail in this mailbox carries a selection outcome."
                      : "No interview mail found in this mailbox."}
                  </p>
                ) : (
                  <ol className="outcome-audit__evidence">
                    {(detail.findings || [])
                      .filter((f) => f.outcome !== "NOT_RELEVANT")
                      .map((finding) => (
                        <li key={finding.id}>
                          <div className="outcome-audit__evidence-head">
                            <span className={`outcome-audit__outcome outcome-audit__outcome--${String(finding.outcome).toLowerCase()}`}>
                              {human(finding.outcome)}
                            </span>
                            <span>{Math.round(finding.confidence)}%</span>
                            <span>{day(finding.received_at)}</span>
                          </div>
                          <p className="outcome-audit__subject">{finding.subject || "(no subject)"}</p>
                          <p className="outcome-audit__sub">
                            {finding.sender_name ? `${finding.sender_name} · ` : ""}
                            {finding.sender_email}
                            {finding.company_name ? ` · ${finding.company_name}` : ""}
                          </p>
                          <p className="outcome-audit__rationale">{finding.rationale}</p>
                          {(finding.evidence || []).map((item, index) => (
                            <blockquote key={index}>
                              <em>{human(item.meaning)}</em> — “{item.text}”
                            </blockquote>
                          ))}
                          {(finding.attachment_evidence || []).length > 0 && (
                            <p className="outcome-audit__sub">
                              Attachments:{" "}
                              {(finding.attachment_evidence || [])
                                .map(
                                  (a) =>
                                    `${a.filename} (${a.extraction_status}${a.has_text ? ", text read" : ", no text"})`,
                                )
                                .join("; ")}
                            </p>
                          )}
                          <p className="outcome-audit__sub">
                            Authenticity: <strong>{human(finding.authenticity)}</strong>
                            {(finding.authenticity_detail?.concerns || []).length > 0 &&
                              ` — ${finding.authenticity_detail.concerns.join(" ")}`}
                          </p>
                          <p className="outcome-audit__sub">
                            Pipeline: {finding.pipeline_outcome ? human(finding.pipeline_outcome) : "no event"} (
                            {human(finding.pipeline_agreement)})
                          </p>
                          <p className="outcome-audit__sub">
                            Source: {human(finding.source_type)} ·{" "}
                            {human(finding.evidence_strength)} evidence
                          </p>
                          {(() => {
                            const review = (detail.ollama_reviews || {})[finding.id];
                            if (!review) return null;
                            // Agreement is derived by comparing outcomes, not
                            // taken from the model's own `agrees` field, which
                            // it does not use consistently.
                            const same = review.suggested_outcome === finding.outcome;
                            return (
                              <div
                                className={`outcome-audit__review outcome-audit__review--${
                                  same ? "agree" : "differ"
                                }`}
                              >
                                <div className="outcome-audit__review-head">
                                  <strong>Ollama second opinion</strong>
                                  <span>{review.model}</span>
                                  <span
                                    className={`outcome-audit__strength outcome-audit__strength--${
                                      review.verified ? "strong" : "weak"
                                    }`}
                                  >
                                    {review.verified ? "Citations verified" : "Unverified"}
                                  </span>
                                </div>
                                <p className="outcome-audit__review-row">
                                  <span>Deterministic: <strong>{human(finding.outcome)}</strong></span>
                                  <span>
                                    Pipeline:{" "}
                                    <strong>
                                      {finding.pipeline_outcome
                                        ? human(finding.pipeline_outcome)
                                        : "no event"}
                                    </strong>
                                  </span>
                                  <span>
                                    Ollama:{" "}
                                    <strong>{human(review.suggested_outcome)}</strong>
                                  </span>
                                  <span>{same ? "Agrees" : "Disagrees"}</span>
                                </p>
                                {review.quoted_evidence && (
                                  <blockquote>“{review.quoted_evidence}”</blockquote>
                                )}
                                <p className="outcome-audit__rationale">{review.reasoning}</p>
                                <p className="outcome-audit__sub">
                                  Cited message {review.cited_message_id || "—"}
                                  {review.cited_attachment
                                    ? ` · attachment ${review.cited_attachment}`
                                    : ""}
                                  {review.cited_company ? ` · ${review.cited_company}` : ""}
                                  {review.is_bulk_campaign ? " · reads as a bulk campaign" : ""}
                                </p>
                                {!review.verified && (
                                  <p className="outcome-audit__warnbox">
                                    Not acted on — {review.verification_problems}
                                  </p>
                                )}
                                <p className="outcome-audit__sub">
                                  {same
                                    ? "Advisory only. Both readings agree; approval still requires the application-level checks above."
                                    : "Advisory only. A disagreement is a prompt to read the mail, not a status change."}
                                </p>
                              </div>
                            );
                          })()}
                        </li>
                      ))}
                  </ol>
                )}

                {(detail.gaps || []).length > 0 && (
                  <>
                    <h3>Pipeline gaps for this candidate</h3>
                    <ul className="outcome-audit__gaplist">
                      {detail.gaps.map((gap) => (
                        <li key={gap.id}>
                          <strong>{human(gap.gap_type)}</strong> ({gap.severity}) — {gap.detail}
                        </li>
                      ))}
                    </ul>
                  </>
                )}

                {(detail.approvals || []).length > 0 && (
                  <>
                    <h3>Approval history</h3>
                    <ul className="outcome-audit__gaplist">
                      {detail.approvals.map((item) => (
                        <li key={item.id}>
                          {when(item.created_at)} — {item.decision} {human(item.requested_outcome)} by{" "}
                          {item.approved_by}
                          {item.applied ? ` → status "${item.applied_system_status}"` : " (not applied)"}
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </>
            )}
          </aside>
        </div>
      )}
    </div>
  );
}

export default OutcomeAuditPanel;
