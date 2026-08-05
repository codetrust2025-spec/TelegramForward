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

const OUTCOMES = [
  "INTERVIEW_INVITE",
  "INTERVIEW_RESCHEDULED",
  "INTERVIEW_CANCELLED",
  "NEXT_ROUND",
  "SHORTLISTED",
  "FINAL_SELECTION",
  "OFFER_INDICATION",
  "VERIFIED_OFFER_LETTER",
  "JOINING_CONFIRMED",
  "BACKGROUND_VERIFICATION",
  "REJECTED",
  "MANUAL_REVIEW_REQUIRED",
  "NOT_RELEVANT",
];

// Outcomes an administrator may approve as a candidate status change. The
// server enforces this too; the UI only avoids offering an action that would
// be refused.
const APPROVABLE = new Set(OUTCOMES.filter(
  (value) => value !== "NOT_RELEVANT" && value !== "MANUAL_REVIEW_REQUIRED",
));

const AUTHENTICITY = ["PASS", "PARTIAL", "UNVERIFIED", "SUSPICIOUS"];

const human = (value) =>
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

const SUMMARY_TILES = [
  ["total_connected_mailboxes", "Connected mailboxes"],
  ["mailboxes_scanned", "Scanned"],
  ["mailboxes_failed", "Failed to scan"],
  ["candidates_with_interview_invites", "Interview invites"],
  ["candidates_shortlisted", "Shortlisted"],
  ["candidates_next_round", "Next round"],
  ["candidates_final_selection", "Final selections"],
  ["candidates_offer_indication", "Offer indications"],
  ["candidates_verified_offer_letters", "Verified offer letters"],
  ["candidates_joining_confirmed", "Joining confirmed"],
  ["candidates_background_verification", "Background verification"],
  ["candidates_rejected", "Rejected"],
  ["candidates_no_outcome", "No outcome found"],
  ["candidates_manual_review", "Need manual review"],
  ["candidates_status_mismatch", "Status mismatches"],
  ["candidates_conflicting_evidence", "Conflicting evidence"],
  ["candidates_suspicious_evidence", "Suspicious evidence"],
  ["emails_missed_or_misclassified", "Mail missed / misclassified"],
  ["sync_or_queue_failures", "Sync or queue failures"],
];

export function OutcomeAuditPanel() {
  const { confirm } = useConfirm();
  const [summary, setSummary] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [gaps, setGaps] = useState([]);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [tab, setTab] = useState("candidates");

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

  const query = useMemo(() => {
    const params = new URLSearchParams();
    if (filters.candidate.trim()) params.set("candidate", filters.candidate.trim());
    if (filters.company.trim()) params.set("company", filters.company.trim());
    if (filters.outcome !== "ALL") params.set("outcome", filters.outcome);
    if (filters.authenticity !== "ALL") params.set("authenticity", filters.authenticity);
    if (filters.sync_status !== "ALL") params.set("sync_status", filters.sync_status);
    if (filters.min_confidence) params.set("min_confidence", filters.min_confidence);
    if (filters.manual_review) params.set("manual_review", "1");
    if (filters.mismatch) params.set("mismatch", "1");
    return params.toString();
  }, [filters]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const suffix = query ? `?${query}` : "";
      const [summaryBody, candidateBody, gapBody] = await Promise.all([
        request(`/api/mail-outcome-audit/summary${suffix}`),
        request(`/api/mail-outcome-audit/candidates${suffix}`),
        request(`/api/mail-outcome-audit/gaps?limit=300`),
      ]);
      setSummary(summaryBody.summary || null);
      setCandidates(candidateBody.candidates || []);
      setGaps(gapBody.gaps || []);
    } catch (exc) {
      setError(exc.message || "Could not load the audit report");
    } finally {
      setLoading(false);
    }
  }, [query]);

  useEffect(() => {
    load();
  }, [load]);

  const runAudit = useCallback(async () => {
    const ok = await confirm({
      title: "Run the mail outcome audit",
      message:
        "This reads every authorized candidate mailbox and rebuilds the report. " +
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

  const openCandidate = useCallback(
    async (row) => {
      setDetail({ loading: true, candidate: row });
      try {
        const params = new URLSearchParams();
        if (dateFrom) params.set("date_from", dateFrom);
        if (dateTo) params.set("date_to", dateTo);
        const suffix = params.toString() ? `?${params.toString()}` : "";
        const body = await request(
          `/api/mail-outcome-audit/candidates/${encodeURIComponent(row.canonical_candidate_id)}${suffix}`,
        );
        setDetail({ loading: false, ...body });
      } catch (exc) {
        setDetail({ loading: false, candidate: row, error: exc.message });
      }
    },
    [dateFrom, dateTo],
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
          <button type="button" className="cand-btn cand-btn--ghost" onClick={load} disabled={loading}>
            Refresh
          </button>
        </div>
      </header>

      <MailMonitoringTabs active="outcome-audit" />

      {summary?.latest_run && (
        <p className="outcome-audit__runline">
          Last run {when(summary.latest_run.started_at)} · {summary.latest_run.status} ·{" "}
          {summary.latest_run.mode === "REPORT_ONLY" ? "report only" : summary.latest_run.mode} ·{" "}
          {summary.latest_run.messages_examined} messages examined
          {summary.latest_run.incremental ? " (incremental)" : ""}
        </p>
      )}

      {error && <div className="outcome-audit__error">{error}</div>}
      {notice && <div className="outcome-audit__notice">{notice}</div>}

      <section className="outcome-audit__tiles" aria-label="System-wide summary">
        {summary
          ? SUMMARY_TILES.map(([key, label]) => (
              <div className="outcome-audit__tile" key={key}>
                <span className="outcome-audit__tile-value">{summary[key] ?? 0}</span>
                <span className="outcome-audit__tile-label">{label}</span>
              </div>
            ))
          : loading && <InlineLoader label="Loading summary…" />}
      </section>

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
          {OUTCOMES.map((value) => (
            <option key={value} value={value}>
              {human(value)}
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
        <label className="cand-toggle">
          <input
            type="checkbox"
            checked={filters.mismatch}
            onChange={(e) => setFilter("mismatch", e.target.checked)}
          />
          <span>Status mismatches only</span>
        </label>
      </section>

      <nav className="outcome-audit__tabs" aria-label="Audit sections">
        <button
          type="button"
          className={tab === "candidates" ? "is-active" : ""}
          onClick={() => setTab("candidates")}
        >
          Candidates ({candidates.length})
        </button>
        <button
          type="button"
          className={tab === "gaps" ? "is-active" : ""}
          onClick={() => setTab("gaps")}
        >
          Pipeline gaps ({gaps.length})
        </button>
      </nav>

      {loading ? (
        <InlineLoader label="Loading audit results…" />
      ) : tab === "candidates" ? (
        <div className="outcome-audit__table-wrap">
          <table className="outcome-audit__table">
            <thead>
              <tr>
                <th>Candidate</th>
                <th>Gmail</th>
                <th>Mailbox</th>
                <th>Strongest outcome</th>
                <th>Confidence</th>
                <th>Authenticity</th>
                <th>System status</th>
                <th>Companies</th>
                <th>Last sync</th>
                <th aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {candidates.length === 0 ? (
                <tr>
                  <td colSpan={10} className="outcome-audit__empty">
                    No audited mailboxes match these filters. Run the audit if it has not been run yet.
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
                    <td>{human(row.strongest_authenticity) || "—"}</td>
                    <td>
                      {row.system_status || "—"}
                      {row.status_mismatch && (
                        <span className="outcome-audit__warn" title={row.mismatch_detail}>
                          Mismatch
                        </span>
                      )}
                    </td>
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
                    No pipeline gaps recorded.
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

                <h3>Relevant mail, oldest first</h3>
                {(detail.findings || []).filter((f) => f.outcome !== "NOT_RELEVANT").length === 0 ? (
                  <p className="outcome-audit__empty">
                    No mail in this mailbox carries a company outcome.
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
                            {(finding.authenticity_detail?.notes || []).length > 0 &&
                              ` ${finding.authenticity_detail.notes.join(" ")}`}
                          </p>
                          <p className="outcome-audit__sub">
                            Pipeline: {finding.pipeline_outcome ? human(finding.pipeline_outcome) : "no event"} (
                            {human(finding.pipeline_agreement)})
                          </p>
                          {APPROVABLE.has(finding.outcome) && (
                            <div className="outcome-audit__approve">
                              <button
                                type="button"
                                className="cand-btn cand-btn--primary cand-btn--sm"
                                onClick={() => approve(finding, "APPROVED")}
                              >
                                Approve status update
                              </button>
                              <button
                                type="button"
                                className="cand-btn cand-btn--ghost cand-btn--sm"
                                onClick={() => approve(finding, "REJECTED")}
                              >
                                Reviewed, do not apply
                              </button>
                            </div>
                          )}
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
                          {item.error_message ? ` — ${item.error_message}` : ""}
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
