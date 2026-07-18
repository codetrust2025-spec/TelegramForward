import React, { useCallback, useEffect, useMemo, useState } from "react";
import { API } from "../config.js";
import { useConfirm } from "../context/ConfirmContext.jsx";

const request = async (path, options = {}) => {
  const isGet = !options.method || options.method === "GET";
  const join = path.includes("?") ? "&" : "?";
  const response = await fetch(
    `${API}${isGet ? `${path}${join}_offerReview=offer_review_cleanup_v1` : path}`,
    {
      credentials: "include",
      cache: isGet ? "no-store" : undefined,
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
      ...options,
    },
  );
  const body = await response.json().catch(() => ({}));
  if (!response.ok)
    throw new Error(body.detail || body.message || "Request failed");
  return body;
};

const trackedStatuses = new Set([
  "SELECTED",
  "FINAL_SELECTION_CONFIRMED",
  "OFFER_INDICATION",
  "OFFER_IN_PROGRESS",
  "OFFER_APPROVED",
  "OFFER_LETTER_RECEIVED",
  "APPOINTMENT_LETTER_RECEIVED",
  "OFFER_ACCEPTED",
  "JOINING_CONFIRMED",
  "JOINED",
  "POST_SELECTION_ONBOARDING",
  "MANUAL_REVIEW_REQUIRED",
]);
const hiddenReviews = new Set(["IGNORED", "FALSE_POSITIVE", "DUPLICATE"]);
const human = (value) =>
  String(value || "")
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
const formatTime = (value) => {
  if (!value) return "Never";
  const date = new Date(value);
  const today = new Date();
  const label =
    date.toDateString() === today.toDateString()
      ? "Today"
      : date.toLocaleDateString();
  return `${label}, ${date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}`;
};
const initials = (name) =>
  String(name || "?")
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
const isVisibleEvent = (event) =>
  trackedStatuses.has(event.primary_status) &&
  !hiddenReviews.has(event.review_status) &&
  event.visible_in_offer_review !== false &&
  ((event.primary_status === "MANUAL_REVIEW_REQUIRED" &&
    (event.validation_status || event.structured_result?.validation_status) ===
      "RETRY_PENDING") ||
    (Number(event.confidence || 0) >= 0.8 &&
      Boolean(event.structured_result?.evidence?.length)));

export function SummaryCard({ tone, icon, value, title, subtitle }) {
  return (
    <article className={`sot-summary-card is-${tone}`}>
      <span className="sot-summary-icon" aria-hidden="true">
        {icon}
      </span>
      <div>
        <strong>{value ?? 0}</strong>
        <h3>{title}</h3>
        <p>{subtitle}</p>
      </div>
    </article>
  );
}

export function MailboxMetric({ icon, label, value, tone = "blue" }) {
  return (
    <article className={`sot-mailbox-metric is-${tone}`}>
      <span>{icon}</span>
      <div>
        <small>{label}</small>
        <strong>{value}</strong>
      </div>
    </article>
  );
}

export function StatusBadge({ status }) {
  const normalized =
    {
      RECONNECT_REQUIRED: "Reconnect Required",
      PAUSED: "Monitoring Paused",
      SYNC_QUEUED: "Sync Queued",
      SYNCING: "Syncing Emails",
      CONNECTED: "Monitoring Active",
    }[status] || human(status);
  return (
    <span className={`sot-status-badge is-${status.toLowerCase()}`}>
      <i />
      {normalized}
    </span>
  );
}

export function FilterButton({ active, children, onClick }) {
  return (
    <button
      className={`sot-filter-button ${active ? "active" : ""}`}
      onClick={onClick}
    >
      {children}
    </button>
  );
}

export function SearchInput({ value, onChange }) {
  return (
    <label className="sot-search">
      <span aria-hidden="true">⌕</span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Search candidate or Gmail account"
      />
    </label>
  );
}

export function ActionMenu({ row, busy, onAction }) {
  const reconnect = row.uiStatus === "RECONNECT_REQUIRED";
  const selectAction = (event, action) => {
    event.currentTarget.closest("details")?.removeAttribute("open");
    onAction(action, row);
  };
  return (
    <details className="sot-action-menu">
      <summary aria-label={`More actions for ${row.candidate.name}`}>
        •••
      </summary>
      <div>
        <button
          disabled={busy}
          onClick={(event) => selectAction(event, "verify")}
        >
          Verify Connection
        </button>
        <button
          disabled={busy}
          onClick={(event) => selectAction(event, "sync")}
        >
          Sync Now
        </button>
        <button
          disabled={busy}
          onClick={(event) =>
            selectAction(
              event,
              row.mailbox.monitoring_enabled ? "pause" : "resume",
            )
          }
        >
          {row.mailbox.monitoring_enabled
            ? "Pause Monitoring"
            : "Resume Monitoring"}
        </button>
        {reconnect && (
          <button
            disabled={busy}
            className="danger"
            onClick={(event) => selectAction(event, "reconnect")}
          >
            Reconnect Gmail
          </button>
        )}
        <button
          disabled={busy}
          className="danger"
          onClick={(event) => selectAction(event, "disconnect")}
        >
          Disconnect Gmail
        </button>
      </div>
    </details>
  );
}

export function MailboxRow({ row, busy, onView, onAction }) {
  const needsReview = Number(row.stats.pending_reviews || 0);
  const syncStatus = String(row.stats.latest_sync_status || "").toUpperCase();
  const syncActive = ["QUEUED", "RUNNING"].includes(syncStatus);
  return (
    <>
      <tr className="sot-mailbox-row">
        <td data-label="Candidate">
          <div className="sot-candidate">
            <span className="sot-avatar">{initials(row.candidate.name)}</span>
            <div>
              <strong>{row.candidate.name}</strong>
              <small>
                Candidate ID: {row.candidate.phone || row.candidate.id}
              </small>
            </div>
          </div>
        </td>
        <td data-label="Gmail Account">{row.mailbox.email_address}</td>
        <td data-label="Status">
          <StatusBadge status={row.uiStatus} />
        </td>
        <td data-label="Relevant Emails">{row.stats.important_emails || 0}</td>
        <td data-label="Needs Review">
          <span className={needsReview ? "sot-review-count" : ""}>
            {needsReview ? "● " : ""}
            {needsReview}
          </span>
        </td>
        <td data-label="Last Sync">
          {syncActive ? (
            <span className="sot-sync-progress" role="status">
              <i />
              {syncStatus === "RUNNING"
                ? "Processing emails…"
                : "Waiting to start…"}
            </span>
          ) : (
            formatTime(row.mailbox.last_successful_sync_at)
          )}
        </td>
        <td data-label="Actions">
          <div className="sot-row-actions">
            <button className="sot-outline-button" onClick={() => onView(row)}>
              View Emails
            </button>
            <ActionMenu row={row} busy={busy} onAction={onAction} />
          </div>
        </td>
      </tr>
      {row.uiStatus === "RECONNECT_REQUIRED" && (
        <tr className="sot-reconnect-row">
          <td colSpan={7}>
            <span>
              ⚠ Gmail connection expired. Reconnect to continue monitoring.
            </span>
            <button disabled={busy} onClick={() => onAction("reconnect", row)}>
              Reconnect Gmail
            </button>
          </td>
        </tr>
      )}
    </>
  );
}

export function MailboxTable({ rows, busy, onView, onAction }) {
  return (
    <div className="sot-table-wrap">
      <table className="sot-mailbox-table">
        <thead>
          <tr>
            <th>Candidate</th>
            <th>Gmail Account</th>
            <th>Status</th>
            <th>Relevant Emails</th>
            <th>Needs Review</th>
            <th>Last Sync</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {rows.length ? (
            rows.map((row) => (
              <MailboxRow
                key={row.mailbox.id}
                row={row}
                busy={busy}
                onView={onView}
                onAction={onAction}
              />
            ))
          ) : (
            <tr>
              <td colSpan={7} className="sot-empty">
                No mailboxes match this view.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

export function AdvancedToolsAccordion({
  rows,
  candidateId,
  onCandidate,
  range,
  onRange,
  onRescan,
  busy,
}) {
  const selected = rows.find((row) => row.candidate.id === candidateId);
  return (
    <details className="sot-advanced-tools">
      <summary>
        <span className="sot-tool-icon">⌕</span>
        <div>
          <strong>Advanced Mailbox Tools</strong>
          <small>Technical tools for email recovery and historical sync</small>
        </div>
        <b>⌄</b>
      </summary>
      <div className="sot-advanced-content">
        <label>
          Mailbox
          <select
            value={candidateId}
            onChange={(e) => onCandidate(e.target.value)}
          >
            <option value="">Select mailbox</option>
            {rows.map((row) => (
              <option key={row.mailbox.id} value={row.candidate.id}>
                {row.candidate.name} · {row.mailbox.email_address}
              </option>
            ))}
          </select>
        </label>
        <label>
          From date
          <input
            type="date"
            value={range.range_start}
            max={range.range_end}
            onChange={(e) => onRange({ ...range, range_start: e.target.value })}
          />
        </label>
        <label>
          To date
          <input
            type="date"
            value={range.range_end}
            min={range.range_start}
            onChange={(e) => onRange({ ...range, range_end: e.target.value })}
          />
        </label>
        <button
          className="sot-primary-button"
          disabled={!selected || busy}
          onClick={onRescan}
        >
          Reprocess Stored Emails
        </button>
        {selected && (
          <dl>
            <div>
              <dt>Last successful synchronization</dt>
              <dd>{formatTime(selected.mailbox.last_successful_sync_at)}</dd>
            </div>
            <div>
              <dt>Latest synchronization error</dt>
              <dd>{selected.mailbox.last_error_message || "None"}</dd>
            </div>
          </dl>
        )}
      </div>
    </details>
  );
}

function ReviewQueue({
  events,
  names,
  candidateId,
  onClearCandidate,
  onEvidence,
  onReview,
}) {
  return (
    <section className="sot-content-card">
      <header>
        <div>
          <h2>Review Queue</h2>
          <p>
            Verify AI-detected outcomes before they affect candidate records.
          </p>
        </div>
        <div className="sot-review-header-actions">
          {candidateId && (
            <button onClick={onClearCandidate}>Show all candidates</button>
          )}
          <span>{events.length} records</span>
        </div>
      </header>
      <div className="sot-table-wrap">
        <table className="sot-review-table">
          <thead>
            <tr>
              <th>Candidate</th>
              <th>Email Subject</th>
              <th>Intent / Lifecycle</th>
              <th>Company</th>
              <th>Confidence</th>
              <th>AI / Validation</th>
              <th>Evidence Summary</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {events.length ? (
              events.map((event) => {
                const fallback =
                  event.structured_result?.classification_source ===
                    "FALLBACK" ||
                  String(event.ai_model || "").includes("fallback:") ||
                  String(event.ai_model || "").includes("ai-unavailable");
                return (
                  <tr key={event.id}>
                    <td>
                      <strong>
                        {names[event.candidate_id] || event.candidate_id}
                      </strong>
                      <small>{formatTime(event.created_at)}</small>
                    </td>
                    <td>{event.subject || "No subject"}</td>
                    <td>
                      <small>
                        {human(
                          event.email_intent ||
                            event.structured_result?.email_intent ||
                            "Unknown",
                        )}
                      </small>
                      <span className="sot-outcome-badge">
                        {human(event.primary_status)}
                      </span>
                    </td>
                    <td>
                      <strong>{event.company_name || "Unknown company"}</strong>
                      <small>{event.job_title || "Unknown role"}</small>
                    </td>
                    <td>
                      {fallback ? (
                        <span
                          className="sot-fallback-confidence"
                          title={
                            event.structured_result?.fallback_reason ||
                            "AI validation unavailable"
                          }
                        >
                          Fallback evidence
                        </span>
                      ) : (
                        `${Math.round(Number(event.confidence) * 100)}%`
                      )}
                    </td>
                    <td>
                      <strong>{event.ai_model || "Not analyzed"}</strong>
                      <small>
                        {human(
                          event.ai_status ||
                            event.structured_result?.ai_status ||
                            "Unknown",
                        )}
                        {" Â· "}
                        {human(
                          event.validation_status ||
                            event.structured_result?.validation_status ||
                            event.review_status,
                        )}
                      </small>
                    </td>
                    <td>
                      {event.evidence_summary ||
                        event.structured_result?.evidence_summary ||
                        event.summary ||
                        "No summary"}
                    </td>
                    <td>
                      <div className="sot-review-actions">
                        <button onClick={() => onEvidence(event.id)}>
                          Evidence
                        </button>
                        <button onClick={() => onReview(event.id, "retry")}>
                          Retry AI
                        </button>
                        {event.review_status === "PENDING" && (
                          <>
                            <button
                              className="approve"
                              onClick={() => onReview(event.id, "approve")}
                            >
                              Approve
                            </button>
                            <button
                              onClick={() =>
                                onReview(event.id, "false-positive")
                              }
                            >
                              Reject
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })
            ) : (
              <tr>
                <td colSpan={8} className="sot-empty">
                  No important detections need review.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function CandidateOutcomes({
  candidates,
  offers,
  selectedId,
  onSelected,
  timeline,
  onEvidence,
  onOfferReview,
}) {
  return (
    <section className="sot-content-card">
      <header>
        <div>
          <h2>Candidates</h2>
          <p>Selection, offer, and joining history in one candidate view.</p>
        </div>
      </header>
      <label className="sot-candidate-picker">
        Candidate
        <select value={selectedId} onChange={(e) => onSelected(e.target.value)}>
          <option value="">Select candidate</option>
          {candidates.map((candidate) => (
            <option key={candidate.id} value={candidate.id}>
              {candidate.name}
            </option>
          ))}
        </select>
      </label>
      {selectedId && (
        <div className="sot-candidate-details">
          <div>
            <h3>Candidate timeline</h3>
            {timeline.length ? (
              <ol className="sot-timeline">
                {timeline.map((item) => (
                  <li key={item.id}>
                    <time>{formatTime(item.created_at)}</time>
                    <strong>{human(item.primary_status)}</strong>
                    <span>
                      {item.company_name || "Unknown company"} ·{" "}
                      {item.job_title || "Unknown role"}
                    </span>
                    <button onClick={() => onEvidence(item.id)}>
                      View evidence
                    </button>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="sot-empty">No timeline events.</p>
            )}
          </div>
          <div>
            <h3>Offer cases</h3>
            {offers
              .filter((offer) => offer.candidate_id === selectedId)
              .map((offer) => (
                <article className="sot-offer-case" key={offer.id}>
                  <strong>{offer.company_name || "Unknown company"}</strong>
                  <span>{offer.job_title || "Unknown role"}</span>
                  <small>
                    {human(offer.verification_status)} ·{" "}
                    {Math.round(Number(offer.confidence) * 100)}%
                  </small>
                  {offer.verification_status === "PENDING_REVIEW" && (
                    <button onClick={() => onOfferReview(offer.id, "verify")}>
                      Verify offer
                    </button>
                  )}
                </article>
              ))}
          </div>
        </div>
      )}
    </section>
  );
}

function Analytics({
  charts,
  flags,
  names,
  aiStatus,
  onConnectionTest,
  onModelTest,
  busy,
}) {
  return (
    <section className="sot-analytics">
      {[
        ["Events by day", charts.events_by_day || [], "day"],
        ["Status distribution", charts.status_distribution || [], "status"],
      ].map(([title, rows, key]) => (
        <article className="sot-content-card" key={title}>
          <h2>{title}</h2>
          {rows.length ? (
            rows.map((row) => (
              <div className="sot-bar" key={row[key]}>
                <span>{human(row[key])}</span>
                <i
                  style={{ width: `${Math.min(100, Number(row.count) * 10)}%` }}
                />
                <strong>{row.count}</strong>
              </div>
            ))
          ) : (
            <p className="sot-empty">No data yet.</p>
          )}
        </article>
      ))}
      <article className="sot-content-card">
        <h2>Conflicts and duplicates</h2>
        {flags.length ? (
          flags.map((flag) => (
            <p key={flag.id}>
              <strong>{human(flag.flag_type)}</strong> ·{" "}
              {names[flag.candidate_id] || flag.candidate_id}
            </p>
          ))
        ) : (
          <p className="sot-empty">No pending risk flags.</p>
        )}
      </article>
      <article className="sot-content-card sot-ai-diagnostics">
        <h2>AI Diagnostics</h2>
        <p>Local Ollama health for selection and offer validation.</p>
        <dl>
          <div>
            <dt>Status</dt>
            <dd>{human(aiStatus?.status || "not checked")}</dd>
          </div>
          <div>
            <dt>Configured model</dt>
            <dd>{aiStatus?.configured_model || "Not configured"}</dd>
          </div>
          <div>
            <dt>Model available</dt>
            <dd>{aiStatus?.model_available ? "Yes" : "No"}</dd>
          </div>
          <div>
            <dt>Last check</dt>
            <dd>{formatTime(aiStatus?.last_checked_at)}</dd>
          </div>
          <div>
            <dt>Response time</dt>
            <dd>
              {aiStatus?.response_time_ms == null
                ? "Unknown"
                : `${aiStatus.response_time_ms} ms`}
            </dd>
          </div>
          <div>
            <dt>Last success</dt>
            <dd>{formatTime(aiStatus?.last_successful_request_at)}</dd>
          </div>
          <div>
            <dt>Average response</dt>
            <dd>
              {aiStatus?.average_response_time_ms == null
                ? "Unknown"
                : `${aiStatus.average_response_time_ms} ms`}
            </dd>
          </div>
          <div>
            <dt>Last error</dt>
            <dd>{aiStatus?.error_code || "None"}</dd>
          </div>
        </dl>
        {aiStatus?.error_message && (
          <p className="sot-ai-error">{aiStatus.error_message}</p>
        )}
        <div className="sot-diagnostic-actions">
          <button disabled={busy} onClick={onConnectionTest}>
            Test Connection
          </button>
          <button disabled={busy} onClick={onModelTest}>
            Test Model Response
          </button>
        </div>
      </article>
    </section>
  );
}

function EvidenceDrawer({ id, onClose, onChanged }) {
  const [event, setEvent] = useState(null);
  useEffect(() => {
    request(`/api/ai-recruitment/events/${id}`).then((body) =>
      setEvent(body.event),
    );
  }, [id]);
  return (
    <aside className="sot-evidence">
      <header>
        <h2>Detection Evidence</h2>
        <button onClick={onClose}>Close</button>
      </header>
      {event ? (
        <>
          <h3>{event.subject}</h3>
          <p>{event.summary}</p>
          <dl>
            <div>
              <dt>Email intent</dt>
              <dd>
                {human(
                  event.email_intent ||
                    event.structured_result?.email_intent ||
                    "Unknown",
                )}
              </dd>
            </div>
            <div>
              <dt>Document</dt>
              <dd>
                {human(
                  event.document_type ||
                    event.structured_result?.document_type ||
                    "None",
                )}
              </dd>
            </div>
            <div>
              <dt>Lifecycle event</dt>
              <dd>
                {human(
                  event.structured_result?.lifecycle_event ||
                    event.primary_status,
                )}
              </dd>
            </div>
            <div>
              <dt>Validation</dt>
              <dd>
                {human(
                  event.validation_status ||
                    event.structured_result?.validation_status ||
                    event.review_status,
                )}
              </dd>
            </div>
            <div>
              <dt>Sender</dt>
              <dd>{event.sender_name || event.sender_email}</dd>
            </div>
            <div>
              <dt>Model</dt>
              <dd>{event.ai_model}</dd>
            </div>
          </dl>
          <p>
            {event.evidence_summary ||
              event.structured_result?.evidence_summary}
          </p>
          <ul>
            {(event.structured_result?.evidence || []).map((item, index) => (
              <li key={index}>
                <strong>{human(item.meaning)}</strong>
                <span>{item.text}</span>
              </li>
            ))}
          </ul>
          <button className="sot-primary-button" onClick={onChanged}>
            Refresh record
          </button>
        </>
      ) : (
        <p>Loading…</p>
      )}
    </aside>
  );
}

export default function RecruitmentMailPanelRedesign() {
  const today = new Date().toISOString().slice(0, 10);
  const { confirm } = useConfirm();
  const [tab, setTab] = useState("mailboxes");
  const [metrics, setMetrics] = useState({
    needs_review: 0,
    selected: 0,
    offers_received: 0,
    offers_accepted: 0,
    joining_confirmed: 0,
    joined: 0,
  });
  const [charts, setCharts] = useState({});
  const [flags, setFlags] = useState([]);
  const [events, setEvents] = useState([]);
  const [offers, setOffers] = useState([]);
  const [candidates, setCandidates] = useState([]);
  const [mailboxes, setMailboxes] = useState([]);
  const [candidateId, setCandidateId] = useState("");
  const [reviewCandidateId, setReviewCandidateId] = useState("");
  const [timeline, setTimeline] = useState([]);
  const [search, setSearch] = useState("");
  const [mailboxFilter, setMailboxFilter] = useState("ALL");
  const [showAddMailbox, setShowAddMailbox] = useState(false);
  const [newMailboxCandidateId, setNewMailboxCandidateId] = useState("");
  const [newMailboxEmail, setNewMailboxEmail] = useState("");
  const [message, setMessage] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [evidenceId, setEvidenceId] = useState(null);
  const [updatedAt, setUpdatedAt] = useState(null);
  const [aiStatus, setAiStatus] = useState(null);
  const [range, setRange] = useState({
    range_start: new Date(Date.now() - 29 * 86400000)
      .toISOString()
      .slice(0, 10),
    range_end: today,
  });

  const load = useCallback(async () => {
    try {
      setMessage("");
      const [dashboard, review, cases, people, ai] = await Promise.all([
        request("/api/ai-recruitment/dashboard").catch(() => ({
          metrics: {},
          charts: {},
          flags: [],
        })),
        request("/api/ai-recruitment/review?limit=100").catch(() => ({
          events: [],
        })),
        request("/api/offer-verification?limit=100").catch(() => ({
          cases: [],
        })),
        request("/candidates?limit=500"),
        request("/api/ai-recruitment/ollama/status?refresh=true").catch(() => ({
          ollama: {
            status: "unavailable",
            error_code: "DIAGNOSTICS_REQUEST_FAILED",
            error_message:
              "AI diagnostics could not be loaded. Candidate and offer data remain available.",
          },
        })),
      ]);
      const candidateList = people.candidates || [];
      const mailboxRows = (
        await Promise.all(
          candidateList.map(async (candidate) => {
            try {
              const result = await request(
                `/api/candidates/${candidate.id}/mailbox`,
              );
              // Multi-mailbox: expand one row per mailbox
              const list =
                result.mailboxes && result.mailboxes.length
                  ? result.mailboxes
                  : result.mailbox
                    ? [{ mailbox: result.mailbox, stats: result.stats || {} }]
                    : [];
              return list.map((entry) => ({
                candidate,
                mailbox: entry.mailbox,
                stats: entry.stats || {},
              }));
            } catch {
              return [];
            }
          }),
        )
      )
        .flat()
        .filter(Boolean);
      setMetrics(dashboard.metrics || {});
      setCharts(dashboard.charts || {});
      setFlags(dashboard.flags || []);
      setEvents((review.events || []).filter(isVisibleEvent));
      setOffers(cases.cases || []);
      setCandidates(candidateList);
      setMailboxes(mailboxRows);
      setAiStatus(ai.ollama || null);
      setUpdatedAt(new Date());
    } catch (error) {
      setMessage(error.message);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);
  useEffect(() => {
    const timer = window.setInterval(() => {
      request("/api/ai-recruitment/ollama/status?refresh=true")
        .then((body) => setAiStatus(body.ollama || null))
        .catch(() => undefined);
    }, 60000);
    return () => window.clearInterval(timer);
  }, []);
  const activeSyncSignature = mailboxes
    .filter((row) =>
      ["QUEUED", "RUNNING"].includes(
        String(row.stats.latest_sync_status || "").toUpperCase(),
      ),
    )
    .map((row) => `${row.mailbox.id}:${row.stats.latest_sync_status}`)
    .join("|");
  useEffect(() => {
    if (!activeSyncSignature) return undefined;
    const timer = window.setInterval(load, 3000);
    return () => window.clearInterval(timer);
  }, [activeSyncSignature, load]);
  useEffect(() => {
    if (!candidateId) {
      setTimeline([]);
      return;
    }
    request(`/api/candidates/${candidateId}/recruitment-timeline`)
      .then((body) => setTimeline(body.events || []))
      .catch((error) => setMessage(error.message));
  }, [candidateId]);

  const run = async (action, feedback = {}) => {
    setBusy(true);
    setMessage("");
    setNotice(feedback.started || "");
    try {
      const result = await action();
      await load();
      setNotice(
        typeof feedback.success === "function"
          ? feedback.success(result)
          : feedback.success || "",
      );
      return result;
    } catch (error) {
      setNotice("");
      setMessage(error.message);
      return null;
    } finally {
      setBusy(false);
    }
  };
  const reconnect = (row) =>
    run(async () => {
      const redirect_uri = `${window.location.origin}/api/candidate-mailboxes/oauth/google/callback`;
      const result = await request(
        `/api/candidates/${row.candidate.id}/mailbox/connect`,
        {
          method: "POST",
          body: JSON.stringify({
            email_address: row.mailbox.email_address,
            redirect_uri,
          }),
        },
      );
      window.location.assign(result.authorization_url);
    });
  const connectNewMailbox = (event) => {
    event.preventDefault();
    const email = newMailboxEmail.trim().toLowerCase();
    if (!newMailboxCandidateId || !email) return;
    run(async () => {
      const redirect_uri = `${window.location.origin}/api/candidate-mailboxes/oauth/google/callback`;
      await request(`/candidates/${newMailboxCandidateId}`, {
        method: "PATCH",
        body: JSON.stringify({ email }),
      });
      const result = await request(
        `/api/candidates/${newMailboxCandidateId}/mailbox/connect`,
        {
          method: "POST",
          body: JSON.stringify({ email_address: email, redirect_uri }),
        },
      );
      if (!result.authorization_url)
        throw new Error("Google authorization could not be started");
      window.location.assign(result.authorization_url);
    });
  };
  const selectNewMailboxCandidate = (candidateId) => {
    setNewMailboxCandidateId(candidateId);
    const candidate = candidates.find(
      (row) => String(row.id) === String(candidateId),
    );
    // Check if this candidate already has mailboxes — if so, clear the field
    // so the user must type the new address rather than accidentally re-adding the same one
    const alreadyHasMailbox = mailboxes.some(
      (row) => String(row.candidate.id) === String(candidateId),
    );
    if (alreadyHasMailbox) {
      setNewMailboxEmail("");
    } else {
      setNewMailboxEmail(
        String(
          candidate?.email ||
            candidate?.email_address ||
            candidate?.gmail_address ||
            candidate?.candidate_email ||
            "",
        )
          .trim()
          .toLowerCase(),
      );
    }
  };
  const disconnect = async (row) => {
    const ok = await confirm({
      title: "Disconnect Gmail?",
      message:
        "Monitoring will stop and the stored OAuth credential will be removed.",
      confirmLabel: "Disconnect",
      variant: "danger",
    });
    if (ok)
      run(
        () =>
          request(
            `/api/candidates/${row.candidate.id}/mailbox?mailbox_id=${encodeURIComponent(row.mailbox.id)}`,
            {
              method: "DELETE",
            },
          ),
        {
          started: `Disconnecting ${row.candidate.name}'s Gmail (${row.mailbox.email_address})…`,
          success: `${row.candidate.name}'s Gmail (${row.mailbox.email_address}) was disconnected.`,
        },
      );
  };
  const mailboxAction = (action, row) => {
    if (action === "reconnect") return reconnect(row);
    if (action === "disconnect") return disconnect(row);
    if (action === "verify")
      return run(
        () =>
          request(`/api/candidates/${row.candidate.id}/mailbox/verify`, {
            method: "POST",
            body: JSON.stringify({ mailbox_id: row.mailbox.id }),
          }),
        {
          started: `Verifying ${row.candidate.name}'s Gmail connection…`,
          success: `${row.candidate.name}'s Gmail connection is verified and healthy.`,
        },
      );
    if (action === "sync")
      return run(
        () =>
          request(`/api/candidates/${row.candidate.id}/mailbox/sync`, {
            method: "POST",
            body: JSON.stringify({ mailbox_id: row.mailbox.id }),
          }),
        {
          started: `Requesting a mailbox sync for ${row.candidate.name}…`,
          success: `${row.candidate.name}'s mailbox sync is queued. Progress will update automatically.`,
        },
      );
    return run(
      () =>
        request(`/api/candidates/${row.candidate.id}/mailbox/settings`, {
          method: "PATCH",
          body: JSON.stringify({
            mailbox_id: row.mailbox.id,
            monitoring_enabled: action === "resume",
          }),
        }),
      {
        started:
          action === "resume"
            ? `Starting monitoring for ${row.candidate.name}…`
            : `Pausing monitoring for ${row.candidate.name}…`,
        success:
          action === "resume"
            ? `Monitoring is active for ${row.candidate.name}.`
            : `Monitoring is paused for ${row.candidate.name}.`,
      },
    );
  };
  const review = async (id, action) => {
    const ok = await confirm({
      title: `${human(action)} detection?`,
      message: "This decision is recorded in the audit log.",
      confirmLabel: human(action),
      variant: action === "approve" ? "success" : "danger",
    });
    if (ok)
      run(() =>
        request(`/api/ai-recruitment/events/${id}/${action}`, {
          method: "POST",
          body: "{}",
        }),
      );
  };
  const offerReview = async (id, action) => {
    const ok = await confirm({
      title: `${human(action)} offer case?`,
      message: "This does not create a payment obligation.",
      confirmLabel: human(action),
      variant: "success",
    });
    if (ok)
      run(() =>
        request(`/api/offer-verification/${id}/${action}`, {
          method: "POST",
          body: "{}",
        }),
      );
  };

  const rows = useMemo(
    () =>
      mailboxes.map((row) => {
        const error = String(
          row.mailbox.last_error_message || "",
        ).toLowerCase();
        const syncStatus = String(
          row.stats.latest_sync_status || "",
        ).toUpperCase();
        const uiStatus =
          syncStatus === "RUNNING"
            ? "SYNCING"
            : syncStatus === "QUEUED"
              ? "SYNC_QUEUED"
              : row.mailbox.connection_status === "ERROR" ||
                  error.includes("expired") ||
                  error.includes("revoked")
                ? "RECONNECT_REQUIRED"
                : !row.mailbox.monitoring_enabled
                  ? "PAUSED"
                  : "CONNECTED";
        return { ...row, uiStatus };
      }),
    [mailboxes],
  );
  const visibleRows = rows.filter((row) => {
    const needle = search.trim().toLowerCase();
    const matchesSearch =
      !needle ||
      `${row.candidate.name} ${row.candidate.phone || ""} ${row.mailbox.email_address}`
        .toLowerCase()
        .includes(needle);
    const connectedStatuses = ["CONNECTED", "SYNC_QUEUED", "SYNCING"];
    const matchesFilter =
      mailboxFilter === "ALL" ||
      row.uiStatus === mailboxFilter ||
      (mailboxFilter === "CONNECTED" &&
        connectedStatuses.includes(row.uiStatus)) ||
      (mailboxFilter === "NEEDS_REVIEW" &&
        Number(row.stats.pending_reviews || 0) > 0);
    return matchesSearch && matchesFilter;
  });
  const availableMailboxCandidates = candidates;
  const names = Object.fromEntries(
    candidates.map((candidate) => [candidate.id, candidate.name]),
  );
  const summary = [
    {
      tone: "amber",
      icon: "△",
      value: metrics.needs_review ?? 0,
      title: "Needs Review",
      subtitle: "Requires your attention",
    },
    {
      tone: "blue",
      icon: "♙",
      value: metrics.selected ?? 0,
      title: "Selected",
      subtitle: "AI-detected selections",
    },
    {
      tone: "blue",
      icon: "✉",
      value: metrics.offers_received ?? 0,
      title: "Offers Received",
      subtitle: "Offer emails detected",
    },
    {
      tone: "green",
      icon: "✓",
      value: metrics.offers_accepted || 0,
      title: "Offers Accepted",
      subtitle: "Candidates accepted",
    },
    {
      tone: "green",
      icon: "♧",
      value: metrics.joining_confirmed ?? 0,
      title: "Joining Confirmed",
      subtitle: "Candidates with confirmed joining arrangements",
    },
    {
      tone: "green",
      icon: "â™§",
      value: metrics.joined ?? 0,
      title: "Joined",
      subtitle: "Candidates confirmed as joined",
    },
  ];
  const viewEmails = (row) => {
    setReviewCandidateId(row.candidate.id);
    setTab("reviews");
  };
  const rescan = () => {
    if (!candidateId) return;
    run(() =>
      request(`/api/candidates/${candidateId}/mailbox/rescan`, {
        method: "POST",
        body: JSON.stringify(range),
      }),
    );
  };
  const testOllama = (kind) =>
    run(async () => {
      const result = await request(`/api/ai-recruitment/ollama/test-${kind}`, {
        method: "POST",
        body: "{}",
      });
      if (result.ollama) setAiStatus(result.ollama);
      if (result.status !== "ok")
        throw new Error(
          result.error_message ||
            result.ollama?.error_message ||
            "Ollama test failed",
        );
    });

  return (
    <main className="sot-page">
      <header className="sot-header">
        <div className="sot-title">
          <span className="sot-brand-avatar">AD</span>
          <div>
            <h1>Selection &amp; Offer Tracking</h1>
            <p>
              AI-detected selections, offers, joining confirmations, and
              candidate updates.
            </p>
          </div>
        </div>
        <div className="sot-header-actions">
          <span
            className={`sot-ai-status is-${aiStatus?.status || "unknown"}`}
            title={aiStatus?.error_message || "Local Ollama status"}
          >
            Ollama {human(aiStatus?.status || "not checked")}
          </span>
          <span>
            Last updated: {updatedAt ? formatTime(updatedAt) : "Loading…"}
          </span>
          <button onClick={load} disabled={busy}>
            ↻ Refresh
          </button>
        </div>
      </header>
      {message && <div className="sot-alert">{message}</div>}
      {notice && (
        <div className="sot-notice" role="status">
          <span aria-hidden="true">✓</span>
          {notice}
        </div>
      )}
      <section className="sot-summary-grid">
        {summary.map((card) => (
          <SummaryCard key={card.title} {...card} />
        ))}
      </section>
      <nav className="sot-tabs">
        {[
          ["reviews", "Review Queue"],
          ["mailboxes", "Mailboxes"],
          ["candidates", "Candidates"],
          ["analytics", "Analytics"],
        ].map(([value, label]) => (
          <button
            key={value}
            className={tab === value ? "active" : ""}
            onClick={() => setTab(value)}
          >
            {label}
          </button>
        ))}
      </nav>
      {tab === "mailboxes" && (
        <>
          <section className="sot-content-card sot-mailbox-overview">
            <div className="sot-overview-head">
              <div>
                <h2>Mailbox Overview</h2>
                <p>
                  Candidate Gmail accounts monitored for important job outcomes.
                </p>
              </div>
              <div className="sot-overview-actions">
                <SearchInput value={search} onChange={setSearch} />
                <button
                  type="button"
                  className="sot-add-mailbox-button"
                  onClick={() => setShowAddMailbox((visible) => !visible)}
                  aria-expanded={showAddMailbox}
                >
                  {showAddMailbox ? "Close" : "+ Add candidate Gmail"}
                </button>
              </div>
            </div>
            {showAddMailbox && (
              <form
                className="sot-add-mailbox-form"
                onSubmit={connectNewMailbox}
              >
                <div className="sot-add-mailbox-copy">
                  <h3>Connect a candidate Gmail</h3>
                  <span>
                    Select a candidate and authorize their Gmail securely with
                    Google. You can add multiple Gmail accounts for the same
                    candidate.
                  </span>
                </div>
                <label>
                  Candidate
                  <select
                    value={newMailboxCandidateId}
                    onChange={(event) =>
                      selectNewMailboxCandidate(event.target.value)
                    }
                    required
                  >
                    <option value="">Select candidate</option>
                    {availableMailboxCandidates.map((candidate) => (
                      <option key={candidate.id} value={candidate.id}>
                        {candidate.name} · {candidate.phone || "no phone"}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Gmail address
                  <input
                    type="email"
                    value={newMailboxEmail}
                    onChange={(event) => setNewMailboxEmail(event.target.value)}
                    placeholder="candidate@gmail.com (or 2nd Gmail)"
                    autoComplete="email"
                    required
                  />
                </label>
                <button
                  type="submit"
                  className="sot-primary-button"
                  disabled={
                    busy || !newMailboxCandidateId || !newMailboxEmail.trim()
                  }
                >
                  {busy ? "Starting…" : "Connect Gmail"}
                </button>
              </form>
            )}
            <section className="sot-mailbox-metrics">
              <MailboxMetric
                icon="✉"
                label="Total Mailboxes"
                value={rows.length}
              />
              <MailboxMetric
                icon="✓"
                label="Connected"
                value={
                  rows.filter((row) => row.uiStatus === "CONNECTED").length +
                  rows.filter((row) =>
                    ["SYNC_QUEUED", "SYNCING"].includes(row.uiStatus),
                  ).length
                }
                tone="green"
              />
              <MailboxMetric
                icon="!"
                label="Reconnect Required"
                value={
                  rows.filter((row) => row.uiStatus === "RECONNECT_REQUIRED")
                    .length
                }
                tone="red"
              />
              <MailboxMetric
                icon="◉"
                label="Needs Review"
                value={
                  rows.filter(
                    (row) => Number(row.stats.pending_reviews || 0) > 0,
                  ).length
                }
                tone="amber"
              />
            </section>
            <div className="sot-filter-row">
              {[
                ["ALL", "All"],
                ["CONNECTED", "Connected"],
                ["RECONNECT_REQUIRED", "Reconnect Required"],
                ["NEEDS_REVIEW", "Needs Review"],
              ].map(([value, label]) => (
                <FilterButton
                  key={value}
                  active={mailboxFilter === value}
                  onClick={() => setMailboxFilter(value)}
                >
                  {label}
                </FilterButton>
              ))}
            </div>
            <MailboxTable
              rows={visibleRows}
              busy={busy}
              onView={viewEmails}
              onAction={mailboxAction}
            />
          </section>
          <AdvancedToolsAccordion
            rows={rows}
            candidateId={candidateId}
            onCandidate={setCandidateId}
            range={range}
            onRange={setRange}
            onRescan={rescan}
            busy={busy}
          />
        </>
      )}
      {tab === "reviews" && (
        <ReviewQueue
          events={
            reviewCandidateId
              ? events.filter(
                  (event) => event.candidate_id === reviewCandidateId,
                )
              : events
          }
          names={names}
          candidateId={reviewCandidateId}
          onClearCandidate={() => setReviewCandidateId("")}
          onEvidence={setEvidenceId}
          onReview={review}
        />
      )}
      {tab === "candidates" && (
        <CandidateOutcomes
          candidates={candidates}
          offers={offers}
          selectedId={candidateId}
          onSelected={setCandidateId}
          timeline={timeline}
          onEvidence={setEvidenceId}
          onOfferReview={offerReview}
        />
      )}
      {tab === "analytics" && (
        <Analytics
          charts={charts}
          flags={flags}
          names={names}
          aiStatus={aiStatus}
          onConnectionTest={() => testOllama("connection")}
          onModelTest={() => testOllama("model")}
          busy={busy}
        />
      )}
      {evidenceId && (
        <EvidenceDrawer
          id={evidenceId}
          onClose={() => setEvidenceId(null)}
          onChanged={load}
        />
      )}
    </main>
  );
}
