"""Patch candidatesModule.jsx for compact Works pending layout."""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
TARGET = ROOT / "dashboard" / "src" / "candidates" / "candidatesModule.jsx"

HELPERS = r'''
const PENDING_WORK_KIND_ICONS = {
  missing_resume: "📄",
  payment_due: "₹",
  missing_follow_up: "💬",
  missing_reference: "👤",
  missing_phone: "📞",
};
const PENDING_WORK_KIND_ORDER = [
  "missing_resume",
  "payment_due",
  "missing_follow_up",
  "missing_reference",
  "missing_phone",
];

function normalizeCandName(name) {
  return String(name || "").trim().toLowerCase().replace(/\s+/g, " ");
}

function compactStageMeta(stage) {
  const meta = fR(stage);
  const icons = {
    completed: "✓",
    in_progress: "●",
    fail: "✕",
    dropped: "—",
  };
  const signCls = {
    completed: "cand-badge__sign--done",
    in_progress: "cand-badge__sign--active",
    fail: "cand-badge__sign--fail",
    dropped: "cand-badge__sign--dropped",
  };
  return {
    ...meta,
    icon: icons[stage] || "?",
    signCls: signCls[stage] || "cand-badge__sign--dropped",
  };
}

function CandStageDot({ stage }) {
  if (stage !== "completed" && stage !== "in_progress") {
    return null;
  }
  const meta = compactStageMeta(stage);
  return <span className={`cand-stage-dot cand-stage-dot--${stage}`} title={meta.label} aria-hidden={true} />;
}

function CandCompactStatusBadge({ stage }) {
  const meta = compactStageMeta(stage);
  return (
    <span className={`cand-badge ${meta.cls}`} title={meta.label}>
      <span className={`cand-badge__sign ${meta.signCls}`.trim()} aria-hidden={true}>{meta.icon}</span>
      <span className="cand-badge__text">{meta.label}</span>
    </span>
  );
}

function CandServiceTypeCell({ row }) {
  if (row.service_type === "round_wise") {
    const round = row.interview_round ? `R${row.interview_round}` : null;
    return (
      <span className="cand-svc cand-svc--round" title="Round-wise interview support">
        <span className="cand-svc__kind">Round</span>
        {round && <span className="cand-svc__round">{round}</span>}
      </span>
    );
  }
  return <span className="cand-svc cand-svc--profile" title="Profile service">Profile</span>;
}

function formatCompactCandDate(value) {
  if (!value) {
    return "—";
  }
  try {
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) {
      return value;
    }
    return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short" });
  } catch {
    return value;
  }
}

function CandResumeCellCompact({ row }) {
  const count = Number(row.resume_count) || (Array.isArray(row.resumes) ? row.resumes.length : 0);
  return (
    <div className="cand-resume-cell cand-resume-cell--compact">
      {count > 0 ? (
        <span className="cand-pay-proofs cand-pay-proofs--btn cand-resume-view cand-resume-view--compact" title={`${count} resume version${count === 1 ? "" : "s"}`}>
          <span aria-hidden={true}>📄</span>
        </span>
      ) : (
        <span className="cand-btn cand-btn--ghost cand-btn--xs cand-resume-upload cand-resume-upload--compact" title="No resume uploaded yet">↑</span>
      )}
    </div>
  );
}

function groupPendingWorks(works) {
  const groups = new Map();
  for (const item of works || []) {
    const kind = item.kind || "other";
    if (!groups.has(kind)) {
      groups.set(kind, { kind, label: item.label || kind, items: [] });
    }
    groups.get(kind).items.push(item);
  }
  return PENDING_WORK_KIND_ORDER.filter((kind) => groups.has(kind)).map((kind) => groups.get(kind));
}

function collectPendingWorksFromRows(rows, isAdmin) {
  const works = [];
  for (const row of rows || []) {
    if (row.stage !== "in_progress") {
      continue;
    }
    const base = {
      candidate_id: row.id,
      candidate_name: row.name || "",
      reference: row.reference || "",
      technology: row.technology || "",
    };
    const resumeCount = Number(row.resume_count) || (Array.isArray(row.resumes) ? row.resumes.length : 0);
    if (resumeCount === 0) {
      works.push({ ...base, id: `missing_resume:${row.id}`, kind: "missing_resume", label: "Upload resume", detail: "" });
    }
    if (row.needs_followup) {
      works.push({ ...base, id: `payment_due:${row.id}`, kind: "payment_due", label: "Payment pending", detail: row.follow_up || "" });
    }
    if (!String(row.follow_up || "").trim() && row.needs_followup) {
      works.push({ ...base, id: `missing_follow_up:${row.id}`, kind: "missing_follow_up", label: "Add follow-up remark", detail: "" });
    }
    if (!String(row.phone || "").trim()) {
      works.push({ ...base, id: `missing_phone:${row.id}`, kind: "missing_phone", label: "Add phone number", detail: "" });
    }
    if (isAdmin && !String(row.reference || "").trim()) {
      works.push({ ...base, id: `missing_reference:${row.id}`, kind: "missing_reference", label: "Assign referrer", detail: "" });
    }
  }
  return works;
}

function CandPendingWorksSidebar({
  works = [],
  loading = false,
  onOpenCandidate,
  onFilterWorks,
  filterActive = false,
}) {
  const [collapsed, setCollapsed] = w.useState(false);
  const groups = w.useMemo(() => groupPendingWorks(works), [works]);
  const taskCount = works.length;
  const candidateCount = w.useMemo(() => new Set(works.map((item) => normalizeCandName(item.candidate_name))).size, [works]);
  const filterTitle = candidateCount !== taskCount
    ? `Show ${candidateCount} candidates with ${taskCount} pending tasks`
    : `Show ${taskCount} candidate${taskCount === 1 ? "" : "s"} with pending work`;

  if (!loading && works.length === 0) {
    return (
      <section className="cand-pending-works cand-pending-works--sidebar">
        <header className="cand-pending-works__head">
          <h3 className="cand-pending-works__title">Pending works</h3>
        </header>
        <div className="cand-pending-works__body">
          <p className="cand-pending-works__empty">All clear — no pending tasks.</p>
        </div>
      </section>
    );
  }

  return (
    <section className={`cand-pending-works${collapsed ? " cand-pending-works--collapsed" : ""} cand-pending-works--sidebar`}>
      <header className="cand-pending-works__head">
        <div>
          <h3 className="cand-pending-works__title">Pending works</h3>
        </div>
        <div className="cand-pending-works__actions">
          {works.length > 0 && onFilterWorks && (
            <button
              type="button"
              className={`cand-btn cand-btn--ghost cand-btn--xs${filterActive ? " cand-btn--active" : ""}`}
              onClick={onFilterWorks}
              title={filterTitle}
            >
              {filterActive ? "Show all" : `Filter (${taskCount})`}
            </button>
          )}
          <button type="button" className="cand-btn cand-btn--ghost cand-btn--xs" onClick={() => setCollapsed((v) => !v)} aria-expanded={!collapsed}>
            {collapsed ? "Expand" : "Collapse"}
          </button>
        </div>
      </header>
      {!collapsed && (
        <div className="cand-pending-works__body">
          {loading && <p className="cand-pending-works__empty">Loading pending works…</p>}
          {!loading && groups.map((group) => (
            <div className="cand-pending-works__group" key={group.kind}>
              <h4 className="cand-pending-works__group-title">
                <span aria-hidden={true}>{PENDING_WORK_KIND_ICONS[group.kind] || "•"}</span>
                {group.label}
                <span className="cand-pending-works__group-count">{group.items.length}</span>
              </h4>
              <ul className="cand-pending-works__list">
                {group.items.map((item) => (
                  <li className="cand-pending-works__item" key={item.id}>
                    <button type="button" className="cand-pending-works__link" onClick={() => onOpenCandidate == null ? undefined : onOpenCandidate(item)}>
                      <span className="cand-pending-works__name">{item.candidate_name}</span>
                      {item.technology && <span className="cand-pending-works__tech">{item.technology}</span>}
                      {item.reference && <span className="cand-pending-works__ref">{item.reference}</span>}
                      {item.detail && <span className="cand-pending-works__detail">{item.detail}</span>}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function CandAnalyticsDrawer({
  open,
  onClose,
  stats,
  scopeLabel,
  onPayoutsClick,
  handlerView = false,
  handlerName = null,
  month,
  onMonthChange,
  monthOptions,
  onExpensesChanged,
  onShowEarnings,
  onEditPayout,
  scopeReference = null,
}) {
  w.useEffect(() => {
    if (!open) {
      return undefined;
    }
    const onKey = (ev) => {
      if (ev.key === "Escape") {
        onClose == null ? undefined : onClose();
      }
    };
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [open, onClose]);

  if (!open) {
    return null;
  }

  return (
    <s.Fragment>
      <div className="cand-analytics-drawer-backdrop" onClick={onClose} role="presentation" aria-hidden={true} />
      <aside className="cand-analytics-drawer" role="dialog" aria-modal={true} aria-labelledby="cand-analytics-title">
        <header className="cand-analytics-drawer__head">
          <div>
            <h2 id="cand-analytics-title" className="cand-analytics-drawer__title">Analytics</h2>
            <p className="cand-analytics-drawer__sub">
              Top performers, handler payouts, and technology breakdown
              {scopeLabel ? ` · ${scopeLabel}` : ""}
            </p>
          </div>
          <button type="button" className="cand-modal-close" onClick={onClose} aria-label="Close analytics">×</button>
        </header>
        <div className="cand-analytics-drawer__body">
          {stats && (
            <_Component26
              stats={stats}
              month={month}
              onMonthChange={onMonthChange}
              monthOptions={monthOptions}
              onExpensesChanged={onExpensesChanged}
              onShowEarnings={onShowEarnings}
              onEditPayout={onEditPayout}
              handlerView={handlerView}
              handlerName={handlerName}
              scopeReference={scopeReference}
            />
          )}
          {onPayoutsClick && (
            <button type="button" className="cand-btn cand-btn--ghost cand-btn--sm" style={{ marginTop: 10 }} onClick={onPayoutsClick}>
              Open full payout board →
            </button>
          )}
        </div>
      </aside>
    </s.Fragment>
  );
}

'''


def main() -> None:
    text = TARGET.read_text(encoding="utf-8")

    if "cand-page--compact" in text:
        print("Already patched")
        return

    # Insert helpers before mR()
    anchor = "function mR() {"
    if anchor not in text:
        raise SystemExit("mR anchor not found")
    text = text.replace(anchor, HELPERS + anchor, 1)

    # J8 signature + compact stats shell
    text = text.replace(
        "function J8({\n  stats: e,\n  scopeLabel: t,\n  onPayoutsClick: r,\n  handlerView: n = false,\n  handlerName: a = null,\n  scopeReference: scopeRef = null\n}) {",
        "function J8({\n  stats: e,\n  scopeLabel: t,\n  onPayoutsClick: r,\n  onAnalyticsClick: analyticsClick = null,\n  compact: compactStats = false,\n  handlerView: n = false,\n  handlerName: a = null,\n  scopeReference: scopeRef = null\n}) {",
        1,
    )
    text = text.replace(
        'return <div className="cand-stats"><div className="cand-stat-card">',
        'return <div className={compactStats ? "cand-stats cand-stats--compact" : "cand-stats"}><div className="cand-stat-card">',
        1,
    )
    text = text.replace(
        '<div className="cand-stat-sub">After referral {cr(referralCommission)} · completed {cr(companyCompleted)}</div></div>',
        '<div className="cand-stat-sub" title={`After referral ${cr(referralCommission)} · completed ${cr(companyCompleted)}`}>{compactStats ? `Completed: ${cr(companyCompleted)}` : `After referral ${cr(referralCommission)} · completed ${cr(companyCompleted)}`}</div></div>',
        1,
    )
    text = text.replace(
        "</s.Fragment>}</div></div>{(() => {",
        "</s.Fragment>}</div></div>{!compactStats && (() => {",
        1,
    )
    text = text.replace(
        '})()}<div className="cand-stat-card cand-stat-card--list">',
        '})()}{compactStats && analyticsClick && <button type="button" className="cand-stat-card cand-stat-card--analytics" onClick={() => analyticsClick()}><div className="cand-stat-label">Analytics<span className="cand-stat-arrow" aria-hidden={true}>→</span></div><div className="cand-stat-value">Details</div><div className="cand-stat-sub">Payouts & performers</div></button>}{!compactStats && <div className="cand-stat-card cand-stat-card--list">',
        1,
    )
    text = text.replace(
        '</ul></div></div>;\n}',
        '</ul></div>}{!compactStats ? null : null}</div>;\n}',
        1,
    )
    # fix accidental noop - close list card only when !compactStats
    text = text.replace(
        '</ul></div>}{!compactStats ? null : null}</div>;\n}',
        '</ul></div>}</div>;\n}',
        1,
    )
    text = text.replace(
        '})()}{compactStats && analyticsClick',
        '})()}{!compactStats && <div className="cand-stat-card cand-stat-card--list"><div className="cand-stat-label">Top technologies (company share){t && <span className="cand-stat-scope">{t}</span>}</div><ul className="cand-stat-list">{(e.top_technologies || []).slice(0, 5).map(x => <li key={x.name}><span className="cand-stat-list-name">{x.name}</span><span className="cand-stat-list-value">{cr(x.revenue)}</span></li>)}{(e.top_technologies || []).length === 0 && <li className="cand-stat-list-empty">No data yet.</li>}</ul></div>}{compactStats && analyticsClick',
        1,
    )
    # Remove duplicate list card from original tail
    text = text.replace(
        '}{!compactStats && <div className="cand-stat-card cand-stat-card--list"><div className="cand-stat-label">Top technologies (company share){t && <span className="cand-stat-scope">{t}</span>}</div><ul className="cand-stat-list">{(e.top_technologies || []).slice(0, 5).map(x => <li key={x.name}><span className="cand-stat-list-name">{x.name}</span><span className="cand-stat-list-value">{cr(x.revenue)}</span></li>)}{(e.top_technologies || []).length === 0 && <li className="cand-stat-list-empty">No data yet.</li>}</ul></div>}{compactStats && analyticsClick',
        '}{compactStats && analyticsClick',
        1,
    )

    # analytics open state
    text = text.replace(
        "const [ro, setRo] = w.useState(false);",
        "const [ro, setRo] = w.useState(false);\n  const [analyticsOpen, setAnalyticsOpen] = w.useState(false);",
        1,
    )

    # pending works memos before return
    insert_before = "  return <div className=\"cand-page\">"
    pending_block = '''  const pendingWorks = w.useMemo(() => {
    const fromStats = (c == null ? undefined : c.pending_works) || [];
    return fromStats.length ? fromStats : collectPendingWorksFromRows(i, a);
  }, [c, i, a]);
  const pendingWorkNames = w.useMemo(() => new Set(pendingWorks.map((work) => normalizeCandName(work.candidate_name))), [pendingWorks]);
  const pendingWorksBadge = (c == null ? undefined : c.pending_works_candidates) ?? pendingWorkNames.size;
  const pendingWorksTitle = (c == null ? undefined : c.pending_count) > 0
    ? "Show only candidates with a pending balance"
    : "Show candidates with pending work tasks";
  const openPendingWorkCandidate = w.useCallback((work) => {
    const key = normalizeCandName(work.candidate_name);
    const match = i.find((row) => normalizeCandName(row.name) === key || row.id === work.candidate_id);
    if (match) {
      I(match);
      return;
    }
    v(`Could not open ${work.candidate_name || "candidate"} — try “All time” month filter.`);
  }, [i]);
'''
    text = text.replace(insert_before, pending_block + insert_before, 1)

    # Replace return block using regex from return to closing of CandidatesPanel
    new_return = r'''  return (
    <div className="cand-page cand-page--compact">
      <div className="cand-page-sticky">
        <header className="cand-header cand-header--compact">
          <div className="cand-header-titles">
            <h2 className="cand-title">Candidates</h2>
            <p className="cand-subtitle">{n ? `Your referred candidates and earnings${t ? ` — ${t}` : ""}.` : "Tracker for every profile you take on — replaces the old Profiles list update Form sheet."}</p>
          </div>
          <div className="cand-header-actions">
            <button type="button" className="cand-btn cand-btn--ghost cand-btn--icon" onClick={() => setRo(true)} title="Active list">☰</button>
            <button type="button" className="cand-btn cand-btn--ghost cand-btn--icon" onClick={() => triggerRosterDownload({ month: "all", reference: T })} title="Download active CSV">↓</button>
            {a && <button type="button" className="cand-btn cand-btn--ghost cand-btn--icon" onClick={ue} title="Manage expenses"><span aria-hidden={true}>₹</span></button>}
            <button type="button" className="cand-btn cand-btn--primary" onClick={q}><span aria-hidden={true}>＋</span> Add</button>
          </div>
        </header>
        <div className="cand-toolbar cand-toolbar--top" role="region" aria-label="Candidate filters">
          <input className="cand-input cand-input--search" placeholder="Search name, tech, reference, phone, notes…" value={E} onChange={ge => b(ge.target.value)} />
          <select className="cand-input" value={m} onChange={ge => _(ge.target.value)} aria-label="Filter by month">{Le.map(ge => <option value={ge.value} key={ge.value}>{ge.label}</option>)}</select>
          <select className="cand-input" value={g} onChange={ge => p(ge.target.value)}>{dR.map(ge => <option value={ge.value} key={ge.value}>{ge.label}</option>)}</select>
          {a && <select className={`cand-input${T !== "all" ? " cand-input--active" : ""}`} value={T} onChange={ge => S(ge.target.value)} aria-label="Filter by handler / reference" title="Show only candidates referred by this handler">{st.map(ge => <option value={ge.value} key={ge.value}>{ge.label}</option>)}</select>}
          <label className={`cand-toggle${y ? " cand-toggle--on" : ""}${(c == null ? undefined : c.pending_count) > 0 ? " cand-toggle--has-pending" : ""}`} title={pendingWorksTitle}>
            <input type="checkbox" checked={y} onChange={ge => k(ge.target.checked)} />
            <span>Works pending</span>
            {(c == null ? undefined : c.pending_count) > 0 && <span className="cand-toggle-badge">{c.pending_count}</span>}
          </label>
          <div className="cand-toolbar-spacer" />
          <span className="cand-toolbar-count">
            {$e && <span className="cand-toolbar-scope">{$e} ·</span>}
            {T !== "all" && <span className="cand-toolbar-scope cand-toolbar-scope--ref">{T} ·</span>}
            {De === ye ? `${ye} candidate${ye === 1 ? "" : "s"}` : `${De} of ${ye}`}
          </span>
        </div>
        {x && <div className="cand-error">{x}</div>}
        {c && <J8 stats={c} scopeLabel={$e} onPayoutsClick={pe} onAnalyticsClick={() => setAnalyticsOpen(true)} compact={true} handlerView={n} handlerName={t} scopeReference={T !== "all" ? T : n ? t : null} />}
      </div>
      <div className="cand-workspace">
        <div className="cand-workspace__main">
          <div className="cand-table-wrap cand-table-wrap--compact">
            <table className="cand-table cand-table--compact">
              <thead>
                <tr>
                  <th>Candidate</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Phone</th>
                  <th>Date</th>
                  <th>Payment</th>
                  <th>Resume</th>
                  <th>Owner</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {f && i.length === 0 ? (
                  <tr><td colSpan={9} className="cand-table-empty">Loading…</td></tr>
                ) : i.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="cand-table-empty">
                      No candidates match these filters. <button type="button" className="cand-link" onClick={q}>Add one</button>.
                    </td>
                  </tr>
                ) : i.map(ge => {
                  const rowTitle = [ge.follow_up, ge.notes].filter(Boolean).join(" · ") || undefined;
                  return (
                    <tr
                      className={`cand-row${ge.needs_followup || pendingWorkNames.has(normalizeCandName(ge.name)) ? " cand-row--pending" : ""}${ge.stage === "completed" ? " cand-row--completed" : ge.stage === "in_progress" ? " cand-row--active" : ""}`}
                      onClick={() => I(ge)}
                      title={rowTitle}
                      key={ge.id}
                    >
                      <td data-label="Candidate" className="cand-cell-candidate">
                        <CandStageDot stage={ge.stage} />
                        <div className="cand-cell-candidate__body cand-cell-candidate__body--inline">
                          <span className="cand-name">{ge.name}</span>
                          <span className="cand-cell-tech-sep" aria-hidden={true}>·</span>
                          <span className="cand-cell-tech-inline">{ge.technology || "—"}</span>
                        </div>
                      </td>
                      <td data-label="Type" className="cand-cell-type"><CandServiceTypeCell row={ge} /></td>
                      <td data-label="Status"><CandCompactStatusBadge stage={ge.stage} /></td>
                      <td data-label="Phone" className="cand-cell-phone" onClick={Ze => Ze.stopPropagation()}><_Component23 phone={ge.phone} inline={true} /></td>
                      <td data-label="Date" className="cand-cell-date">{formatCompactCandDate(ge.date)}</td>
                      <td data-label="Payment"><_Component27 row={ge} onViewProofs={Z} /></td>
                      <td data-label="Resume" className="cand-cell-resume" onClick={Ze => Ze.stopPropagation()}><CandResumeCellCompact row={ge} /></td>
                      <td data-label="Owner" className="cand-cell-owner">{ge.reference || "—"}</td>
                      <td data-label="" className="cand-cell-actions" onClick={Ze => Ze.stopPropagation()}>
                        <button type="button" className="cand-btn cand-btn--ghost cand-btn--xs" onClick={() => I(ge)} title="Edit">✎</button>
                        {a && <button type="button" className="cand-btn cand-btn--ghost cand-btn--xs cand-btn--danger-ghost" onClick={() => Pe(ge)} title="Delete">🗑</button>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
        <aside className="cand-workspace__rail">
          <CandPendingWorksSidebar
            works={pendingWorks}
            loading={f && pendingWorks.length === 0}
            onOpenCandidate={openPendingWorkCandidate}
            onFilterWorks={() => k((checked) => !checked)}
            filterActive={y}
          />
        </aside>
      </div>
      <CandAnalyticsDrawer
        open={analyticsOpen}
        onClose={() => setAnalyticsOpen(false)}
        stats={c}
        scopeLabel={$e}
        onPayoutsClick={pe}
        handlerView={n}
        handlerName={t}
        month={m}
        onMonthChange={_}
        monthOptions={Le}
        onExpensesChanged={fe}
        onShowEarnings={a ? pe : undefined}
        onEditPayout={a ? me : undefined}
        scopeReference={T !== "all" ? T : n ? t : null}
      />
      {L && <X8 initial={C} handlerReference={n ? t : null} lockReference={n} isAdmin={a} onClose={Oe} onSave={Re} />}
      {ce && <_Component28 stats={c} scopeLabel={$e} onClose={() => ee(false)} onManage={a ? ue : undefined} />}
      {J && a && <_Component29 handlerNames={((c == null ? undefined : c.top_performers) || []).map(ge => ge.name).filter(Boolean)} ownedSummary={{
        owed: (c == null ? undefined : c.handler_auto_earnings_total) ?? (c == null ? undefined : c.handler_earnings_total) ?? 0,
        paid: (c == null ? undefined : c.handler_paid_out_total) ?? (c == null ? undefined : c.handler_deductions_total) ?? 0,
        net: (c == null ? undefined : c.net_handler_payout) ?? 0
      }} onClose={() => G(false)} onChanged={fe} />}
      {P && a && <_Component30 handler={P} onClose={() => j(null)} onChanged={fe} />}
      {B && <_Component31 candidate={B} onClose={() => Z(null)} onEdit={ge => I(ge)} />}
      <CandidatesActiveRoster open={ro} onClose={() => setRo(false)} reference={T} />
      <_Component32 open={!!W} title={W == null ? undefined : W.title} message={W == null ? undefined : W.message} onVerified={W == null ? undefined : W.onVerified} onCancel={H} />
    </div>
  );
'''

    pattern = re.compile(r"  return <div className=\"cand-page\">.*?</div>;\n}", re.DOTALL)
    if not pattern.search(text):
        raise SystemExit("return block not found")
    text = pattern.sub(new_return + "\n}", text, count=1)

    TARGET.write_text(text, encoding="utf-8", newline="\n")
    print("Patched", TARGET)


if __name__ == "__main__":
    main()
