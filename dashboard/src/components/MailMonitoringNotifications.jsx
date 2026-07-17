import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { API } from "../config.js";

// Mail Monitoring Notifications track only auto interview slot booking and
// job confirmed monitoring mails.
const TRACKED_CLASSIFICATIONS = [
  "job_selection_confirmed", "offer_received", "offer_accepted",
  "joining_confirmed", "interview_confirmed", "interview_rescheduled",
  "interview_cancelled",
];
const TRACKED_CANDIDATE_STATUSES = ["Selected", "Offer Received", "Offer Accepted", "Joining Confirmed", "Interview Confirmed", "Interview Rescheduled", "Interview Cancelled"];
// Tracked categories for quick-filter buttons
const JOB_CONFIRMED_CLASSIFICATIONS = ["offer_received", "offer_accepted", "job_selection_confirmed"];
const AUTO_BOOKING_CLASSIFICATIONS = ["interview_confirmed", "interview_rescheduled", "interview_cancelled"];
const human = (value) => String(value || "").replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
const when = (value) => value ? new Date(value).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" }) : "—";
const confidence = (value) => `${Math.round(Number(value || 0) * 100)}%`;

async function request(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || "Request failed");
  return body;
}

function navigate(view, detail = {}) {
  window.dispatchEvent(new CustomEvent("teleautomation:navigate", { detail: { view, ...detail } }));
}

function useMailLive(onUpdate) {
  const [status, setStatus] = useState("Offline");
  const callback = useRef(onUpdate);
  callback.current = onUpdate;
  useEffect(() => {
    let socket;
    let stopped = false;
    let retry = 0;
    let timer;
    let heartbeat;
    const seen = new Set();
    const channel = typeof BroadcastChannel !== "undefined" ? new BroadcastChannel("teleautomation-mail-monitoring") : null;
    const receive = (payload) => {
      const id = payload?.event_id;
      if (id && seen.has(id)) return;
      if (id) {
        seen.add(id);
        if (seen.size > 500) seen.delete(seen.values().next().value);
        localStorage.setItem("teleautomation-mail-last-event-id", id);
      }
      callback.current?.(payload);
      if (["slot_auto_booked", "interview_rescheduled", "interview_cancelled"].includes(payload?.event)) {
        window.dispatchEvent(new CustomEvent("teleautomation:slot-booking-updated", { detail: payload }));
      }
      channel?.postMessage(payload);
    };
    if (channel) channel.onmessage = (event) => callback.current?.(event.data);
    const connect = () => {
      if (stopped) return;
      setStatus(retry ? "Reconnecting" : "Offline");
      const scheme = window.location.protocol === "https:" ? "wss" : "ws";
      const last = localStorage.getItem("teleautomation-mail-last-event-id") || "";
      socket = new WebSocket(`${scheme}://${window.location.host}/ws/mail-monitoring?last_event_id=${encodeURIComponent(last)}`);
      socket.onopen = () => {
        retry = 0; setStatus("Live");
        heartbeat = window.setInterval(() => socket?.readyState === WebSocket.OPEN && socket.send(JSON.stringify({ type: "ping" })), 20000);
      };
      socket.onmessage = (event) => {
        try { receive(JSON.parse(event.data)); } catch { /* ignore malformed transport frames */ }
      };
      socket.onclose = () => {
        window.clearInterval(heartbeat);
        if (stopped) return;
        retry += 1; setStatus(retry > 1 ? "Offline" : "Reconnecting");
        timer = window.setTimeout(connect, Math.min(30000, 1000 * (2 ** Math.min(retry, 5))) + Math.random() * 500);
      };
      socket.onerror = () => socket.close();
    };
    request("/api/ai-recruitment/config").then((data) => data.enabled && connect()).catch(() => setStatus("Offline"));
    return () => {
      stopped = true; window.clearTimeout(timer); window.clearInterval(heartbeat);
      channel?.close(); socket?.close();
    };
  }, []);
  return status;
}

export function MailNotificationBell({ compact = false }) {
  const [open, setOpen] = useState(false);
  const [summary, setSummary] = useState({ unread: 0 });
  const [items, setItems] = useState([]);
  const [toast, setToast] = useState(null);
  const wrap = useRef(null);
  const load = useCallback(async () => {
    try {
      const [summaryBody, listBody] = await Promise.all([
        request("/api/mail-monitoring/summary"),
        request("/api/mail-monitoring/notifications?limit=6&offset=0"),
      ]);
      setSummary(summaryBody.summary || {}); setItems(listBody.notifications || []);
    } catch { /* API fallback will retry */ }
  }, []);
  const live = useMailLive((event) => {
    if (["notification_created", "important_mail_detected", "mail_needs_review", "connected"].includes(event?.event)) load();
    if (event?.event === "notification_created") {
      setToast(event); window.setTimeout(() => setToast(null), 6000);
    }
  });
  useEffect(() => {
    load(); const id = window.setInterval(load, 30000); return () => window.clearInterval(id);
  }, [load]);
  useEffect(() => {
    const close = (event) => wrap.current && !wrap.current.contains(event.target) && setOpen(false);
    document.addEventListener("mousedown", close); return () => document.removeEventListener("mousedown", close);
  }, []);
  const action = async (id, name) => {
    await request(`/api/mail-monitoring/notifications/${id}/${name}`, { method: "POST", body: "{}" });
    await load();
  };
  const unread = Number(summary.unread || 0);
  return <div className={`mail-bell${compact ? " mail-bell--compact" : ""}`} ref={wrap}>
    <button type="button" className="mail-bell__button" aria-label={`${unread} unread mail monitoring notifications`} onClick={() => setOpen((value) => !value)}>
      <span aria-hidden>🔔</span>{unread > 0 && <span className="mail-bell__count">{unread > 99 ? "99+" : unread}</span>}
    </button>
    {open && <div className="mail-bell__popover">
      <header><div><strong>Mail monitoring</strong><span className={`mail-live mail-live--${live.toLowerCase()}`}>{live}</span></div><button type="button" onClick={() => { setOpen(false); navigate("mail-notifications"); }}>View all</button></header>
      <div className="mail-bell__list">{items.length ? items.map((item) => <article className={item.is_read ? "" : "is-unread"} key={item.id}>
        <button type="button" className="mail-bell__main" onClick={() => { if (!item.is_read) action(item.id, "read"); setOpen(false); navigate("mail-notifications", { notificationId: item.id }); }}>
          <strong>{item.candidate_name || "Candidate"} · {item.company_name || "Company pending"}</strong>
          <span>{item.candidate_status || human(item.classification)}</span><small>{when(item.email_received_at || item.created_at)}</small>
        </button>
        <button type="button" className="mail-bell__toggle" onClick={() => action(item.id, item.is_read ? "unread" : "read")}>{item.is_read ? "Unread" : "Read"}</button>
      </article>) : <p className="mail-empty">No mail alerts yet.</p>}</div>
    </div>}
    {toast && <button type="button" className="mail-alert-toast" onClick={() => { setToast(null); navigate("mail-notifications", { notificationId: toast.notification_id }); }}><strong>{toast.status || human(toast.classification)}</strong><span>{toast.candidate_name || "Candidate"}{toast.company_name ? ` · ${toast.company_name}` : ""}</span></button>}
  </div>;
}

function NotificationDetail({ item, onClose, onChanged }) {
  const [note, setNote] = useState(item.review_notes || "");
  const [classification, setClassification] = useState(item.classification);
  const [candidateStatus, setCandidateStatus] = useState(item.candidate_status || "Needs Review");
  const act = async (action, changes) => {
    await request(`/api/mail-monitoring/notifications/${item.id}/${action}`, { method: "POST", body: JSON.stringify({ notes: note, changes }) });
    onChanged(); if (action !== "read" && action !== "unread") onClose();
  };
  const viewAudit = async () => {
    const params = new URLSearchParams(item.booking_id ? { booking_id: item.booking_id } : { candidate_id: item.candidate_id });
    const body = await request(`/api/mail-monitoring/booking-audit?${params}`);
    const rows = body.audit || [];
    window.alert(rows.length ? rows.map((row) => `${when(row.created_at)} Â· ${row.booking_status}${row.failure_message ? ` Â· ${row.failure_message}` : ""}`).join("\n") : "No booking audit history found.");
  };
  return <div className="mail-detail-backdrop" role="presentation" onClick={(event) => event.target === event.currentTarget && onClose()}>
    <section className="mail-detail" role="dialog" aria-modal="true" aria-label="Mail monitoring notification">
      <header><div><h3>{item.candidate_status || human(item.classification)}</h3><p>{item.candidate_name || "Candidate"} · {item.company_name || "Company unavailable"}</p></div><button type="button" onClick={onClose} aria-label="Close">×</button></header>
      <dl><div><dt>Email</dt><dd>{item.email_subject || "No subject"}</dd></div><div><dt>From</dt><dd>{item.sender_name || item.sender_email || "Unknown"}</dd></div><div><dt>Received</dt><dd>{when(item.email_received_at)}</dd></div><div><dt>AI confidence</dt><dd>{confidence(item.ai_confidence)}</dd></div>{item.booking_status && <div><dt>Booking</dt><dd>{item.booking_status}</dd></div>}{item.interview_date && <div><dt>Interview</dt><dd>{item.interview_date} Â· {item.interview_time || "Time unavailable"} {item.interview_timezone || ""}</dd></div>}{item.interview_round && <div><dt>Round</dt><dd>{item.interview_round}</dd></div>}</dl>
      <div className="mail-detail__copy"><strong>Summary</strong><p>{item.ai_summary || "No summary available."}</p><strong>Detection reason</strong><p>{item.ai_reason || "Contextual classification"}</p><strong>Recommended action</strong><p>{item.recommended_action || "Review the candidate and email before taking action."}</p></div>
      <label>Review note<textarea value={note} onChange={(event) => setNote(event.target.value)} maxLength={2000} /></label>
      <div className="mail-detail__correction"><select value={classification} onChange={(event) => setClassification(event.target.value)}>{TRACKED_CLASSIFICATIONS.map((value) => <option value={value} key={value}>{human(value)}</option>)}</select><input value={candidateStatus} onChange={(event) => setCandidateStatus(event.target.value)} maxLength={80} /></div>
      <footer>
        {item.booking_id && <button type="button" onClick={() => { onClose(); navigate("daily-ops", { bookingId: item.booking_id, candidateId: item.candidate_id }); }}>View booking</button>}
        <button type="button" onClick={() => { sessionStorage.setItem("cand-open-pending", JSON.stringify({ candidate_id:item.candidate_id, candidate_name:item.candidate_name, action:"contact" })); navigate("candidates", { candidateId: item.candidate_id }); }}>View / contact candidate</button>
        <button type="button" onClick={() => { sessionStorage.setItem("cand-open-pending", JSON.stringify({ candidate_id:item.candidate_id, candidate_name:item.candidate_name, action:"payment-follow-up" })); navigate("candidates", { candidateId: item.candidate_id, action: "payment-follow-up" }); }}>Start payment follow-up</button>
        {item.booking_status && <button type="button" onClick={() => { sessionStorage.setItem("cand-open-pending", JSON.stringify({ candidate_id:item.candidate_id, candidate_name:item.candidate_name, action:"payment-follow-up" })); navigate("candidates", { candidateId: item.candidate_id, action: "payment-follow-up" }); }}>View payment</button>}
        {item.gmail_message_id && <button type="button" onClick={() => window.open(`https://mail.google.com/mail/u/?authuser=${encodeURIComponent(item.candidate_email || "")}#all/${encodeURIComponent(item.gmail_message_id)}`, "_blank", "noopener,noreferrer")}>View email</button>}
        {/^https?:\/\//i.test(item.meeting_link || "") && <button type="button" onClick={() => window.open(item.meeting_link, "_blank", "noopener,noreferrer")}>Open meeting link</button>}
        {item.booking_audit_id && <button type="button" onClick={viewAudit}>View audit history</button>}
        <button type="button" onClick={() => act("false-detection")}>False detection</button>
        <button type="button" onClick={() => act("rerun")}>Re-run AI</button>
        <button type="button" onClick={() => act("correct", { classification, candidate_status: candidateStatus })}>Save correction</button>
        <button type="button" className="mail-primary" onClick={() => act("reviewed")}>Confirm & reviewed</button>
      </footer>
    </section>
  </div>;
}

export function MailMonitoringNotifications() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [summary, setSummary] = useState({ new_offers: 0, selections: 0, joining_confirmations: 0, auto_booked_interviews: 0, needs_review: 0, unread: 0 });
  const [selected, setSelected] = useState(null);
  const [page, setPage] = useState(0);
  const [filters, setFilters] = useState({ search: "", candidate: "", company: "", classification: "", candidateStatus: "", priority: "", read: "", reviewed: "", min: "", max: "", from: "", to: "", sort: "newest" });
  const query = useMemo(() => {
    const params = new URLSearchParams({ limit: "20", offset: String(page * 20), sort: filters.sort });
    for (const [key, value] of Object.entries({ search:filters.search,candidate_id:filters.candidate,company:filters.company,classification:filters.classification,candidate_status:filters.candidateStatus,priority:filters.priority,is_read:filters.read,is_reviewed:filters.reviewed,confidence_min:filters.min ? Number(filters.min)/100 : "",confidence_max:filters.max ? Number(filters.max)/100 : "",date_from:filters.from,date_to:filters.to })) if (value !== "") params.set(key, String(value));
    return params.toString();
  }, [filters, page]);
  const load = useCallback(async () => {
    try { const [list, counts] = await Promise.all([request(`/api/mail-monitoring/notifications?${query}`),request("/api/mail-monitoring/summary")]); setItems(list.notifications || []);setTotal(list.total || 0);setSummary(counts.summary || {}); } catch { /* retain last good state */ }
  }, [query]);
  useMailLive((event) => ["notification_created","important_mail_detected","mail_needs_review","connected"].includes(event?.event) && load());
  useEffect(() => { load(); }, [load]);
  const set = (key) => (event) => { setPage(0); setFilters((value) => ({ ...value, [key]: event.target.value })); };
  const quick = (classification) => { setPage(0); setFilters((value) => ({ ...value, classification })); };
  const act = async (item, action) => { await request(`/api/mail-monitoring/notifications/${item.id}/${action}`, { method:"POST", body:"{}" }); load(); };
  return <section className="mail-monitoring-page">
    <header className="mail-monitoring-page__head"><div><p className="mail-eyebrow">AI MAIL MONITORING</p><h1>Mail Monitoring Notifications</h1><p>Persistent candidate job-status alerts with live delivery and administrator review.</p></div><span className="mail-live mail-live--live">Live</span></header>
    <div className="mail-summary">
      <button onClick={() => quick("offer_received")}><strong>{summary.new_offers || 0}</strong><span>New offers</span></button>
      <button onClick={() => quick("job_selection_confirmed")}><strong>{summary.selections || 0}</strong><span>Selections</span></button>
      <button onClick={() => quick("joining_confirmed")}><strong>{summary.joining_confirmations || 0}</strong><span>Joining confirmations</span></button>
      <button onClick={() => quick("interview_confirmed")}><strong>{summary.auto_booked_interviews || 0}</strong><span>Auto-booked interviews</span></button>
      <button onClick={() => setFilters((value) => ({ ...value, priority:"review_required" }))}><strong>{summary.needs_review || 0}</strong><span>Needs review</span></button>
      <button onClick={() => setFilters((value) => ({ ...value, read:"false" }))}><strong>{summary.unread || 0}</strong><span>Unread alerts</span></button>
    </div>
    <div className="mail-filters">
      <input aria-label="Search notifications" placeholder="Search candidate, email, company or subject" value={filters.search} onChange={set("search")} />
      <input aria-label="Candidate filter" placeholder="Candidate ID" value={filters.candidate} onChange={set("candidate")} />
      <input aria-label="Company filter" placeholder="Company" value={filters.company} onChange={set("company")} />
      <select aria-label="Classification filter" value={filters.classification} onChange={set("classification")}><option value="">All tracked classifications</option>{TRACKED_CLASSIFICATIONS.map((value) => <option value={value} key={value}>{human(value)}</option>)}</select>
      <select aria-label="Candidate status filter" value={filters.candidateStatus} onChange={set("candidateStatus")}><option value="">All candidate statuses</option>{TRACKED_CANDIDATE_STATUSES.map((value) => <option value={value} key={value}>{value}</option>)}</select>
      <select aria-label="Priority filter" value={filters.priority} onChange={set("priority")}><option value="">All priorities</option><option value="high">High</option><option value="medium">Medium</option><option value="review_required">Review required</option><option value="informational">Informational</option></select>
      <select aria-label="Read filter" value={filters.read} onChange={set("read")}><option value="">Read & unread</option><option value="false">Unread</option><option value="true">Read</option></select>
      <select aria-label="Review filter" value={filters.reviewed} onChange={set("reviewed")}><option value="">All review states</option><option value="false">Pending review</option><option value="true">Reviewed</option></select>
      <input aria-label="Minimum confidence" type="number" min="0" max="100" placeholder="Min confidence %" value={filters.min} onChange={set("min")} />
      <input aria-label="Maximum confidence" type="number" min="0" max="100" placeholder="Max confidence %" value={filters.max} onChange={set("max")} />
      <input aria-label="From date" type="date" value={filters.from} onChange={set("from")} /><input aria-label="To date" type="date" value={filters.to} onChange={set("to")} />
      <select aria-label="Sort" value={filters.sort} onChange={set("sort")}><option value="newest">Newest first</option><option value="oldest">Oldest first</option></select>
    </div>
    <div className="mail-table-wrap"><table className="mail-table"><thead><tr><th>Candidate</th><th>Company</th><th>Detected status</th><th>Email subject</th><th>Confidence</th><th>Received</th><th>Review</th><th>Action</th></tr></thead><tbody>
      {items.map((item) => <tr key={item.id} className={item.is_read ? "" : "is-unread"}><td><strong>{item.candidate_name || "Candidate"}</strong><small>{item.candidate_email || ""}</small></td><td>{item.company_name || "—"}<small>{item.job_role || ""}</small></td><td><span className={`mail-priority mail-priority--${item.priority}`}>{item.candidate_status || human(item.classification)}</span></td><td>{item.email_subject || "(no subject)"}</td><td>{confidence(item.ai_confidence)}</td><td>{when(item.email_received_at || item.created_at)}</td><td>{item.is_reviewed ? "Reviewed" : "Pending"}</td><td><button onClick={() => setSelected(item)}>Open</button><button onClick={() => act(item,item.is_read ? "unread" : "read")}>{item.is_read ? "Unread" : "Read"}</button><button onClick={() => act(item,"dismiss")}>Dismiss</button></td></tr>)}
      {!items.length && <tr><td colSpan={8} className="mail-empty">No notifications match these filters.</td></tr>}
    </tbody></table></div>
    <footer className="mail-pagination"><span>{total} notifications</span><button disabled={page===0} onClick={() => setPage((value) => value-1)}>Previous</button><span>Page {page+1}</span><button disabled={(page+1)*20>=total} onClick={() => setPage((value) => value+1)}>Next</button></footer>
    {selected && <NotificationDetail item={selected} onClose={() => setSelected(null)} onChanged={load} />}
  </section>;
}
