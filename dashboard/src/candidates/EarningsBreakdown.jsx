import { useState, useMemo, useCallback, useEffect, Fragment } from "react";
import "./EarningsBreakdown.css";
import { normalizePaymentProofs } from "./paymentProofs.js";

/** "2026-07" → "Jul 2026". Returns "" for anything that is not a real month. */
function monthLabel(value) {
  const match = /^(\d{4})-(\d{2})$/.exec(String(value || "").trim());
  if (!match) return "";
  const date = new Date(Number(match[1]), Number(match[2]) - 1, 1);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString("en-IN", { month: "short", year: "numeric" });
}

/**
 * Name the months a carried-forward balance came from: one month as-is, a run
 * as "Apr – Jun 2026". Gaps are not spelled out — the tooltip carries the
 * amounts, and a span reads better than a list of six months.
 */
function monthSpanLabel(months) {
  const valid = (months || []).filter(m => /^\d{4}-\d{2}$/.test(String(m || "")));
  if (valid.length === 0) return "";
  const sorted = [...valid].sort();
  const first = monthLabel(sorted[0]);
  const last = monthLabel(sorted[sorted.length - 1]);
  if (!first) return "";
  return first === last ? first : `${first} – ${last}`;
}

/**
 * Earnings Breakdown — replaces "Top Performers" tab.
 * Shows per-handler earnings detail with expandable per-candidate rows.
 */
export default function EarningsBreakdown({
  stats,
  allStats = null,
  month,
  onMonthChange,
  monthOptions,
  onAddExpense,
  handlerView = false,
  handlerName = null,
  formatCurrency,
  apiBase = "",
  onViewPaymentProofs,
}) {
  const fmt = formatCurrency || (v => {
    const n = Number(v) || 0;
    return n === 0 ? "₹0" : n < 100000 ? `₹${n.toLocaleString("en-IN")}` : `₹${(n / 100000).toFixed(n % 100000 === 0 ? 0 : 1)}L`;
  });

  const performers = useMemo(() => {
    const src = (stats?.top_performers || []);
    if (handlerView && handlerName) {
      const lc = handlerName.trim().toLowerCase();
      return src.filter(p => (p.name || "").trim().toLowerCase() === lc);
    }
    return src;
  }, [stats, handlerView, handlerName]);

  const [expanded, setExpanded] = useState(null);
  const [sortBy, setSortBy] = useState("net_payable");
  const [handlerCandidates, setHandlerCandidates] = useState({});
  const [loadingCandidates, setLoadingCandidates] = useState(null);

  const candidateCacheKey = useCallback(
    (name, selectedMonth = month) => `${selectedMonth || "all"}::${name}`,
    [month],
  );

  // Fetch candidates for the expanded handler and selected month. The
  // month-scoped key prevents records from a previous month being reused.
  const loadHandlerCandidates = useCallback(async (name, selectedMonth = month) => {
    const cacheKey = `${selectedMonth || "all"}::${name}`;
    setLoadingCandidates(cacheKey);
    try {
      const params = new URLSearchParams();
      if (selectedMonth && selectedMonth !== "all") params.set("month", selectedMonth);
      params.set("reference", name);
      const res = await (await fetch(`${apiBase}/candidates?${params.toString()}`, { credentials: "include" })).json();
      if (res.status === "ok") {
        setHandlerCandidates(prev => ({ ...prev, [cacheKey]: res.candidates || [] }));
      }
    } catch (e) { /* silent */ }
    finally {
      setLoadingCandidates(current => current === cacheKey ? null : current);
    }
  }, [apiBase, month]);

  // Fetch candidates for a specific handler when expanded.
  function toggleExpand(name) {
    if (expanded === name) { setExpanded(null); return; }
    setExpanded(name);
  }

  // Re-fetch the open handler whenever the selected month changes. Parent
  // totals come from `stats`; candidate detail rows use this matching request.
  useEffect(() => {
    if (expanded) loadHandlerCandidates(expanded, month);
  }, [expanded, month, loadHandlerCandidates]);

  const sorted = useMemo(() => {
    const list = [...performers];
    list.sort((a, b) => {
      const av = Math.abs(Number(a[sortBy]) || 0);
      const bv = Math.abs(Number(b[sortBy]) || 0);
      if (bv !== av) return bv - av;
      return (Number(b.revenue_total) || 0) - (Number(a.revenue_total) || 0);
    });
    return list;
  }, [performers, sortBy]);

  // Totals
  const totals = useMemo(() => {
    let commission = 0, salary = 0, owed = 0, paid = 0;
    for (const p of performers) {
      commission += Number(p.commission_total ?? p.auto_earnings_total) || 0;
      salary += Number(p.salary_total) || 0;
      owed += Number(p.auto_earnings_total) || 0;
      paid += Number(p.paid_out_total) || 0;
    }
    return { commission, salary, owed, paid, net: owed - paid };
  }, [performers]);

  function getStatus(net) {
    if (net > 0) return { label: "Owe", cls: "earn-status--owe" };
    if (net < 0) return { label: "Overpaid", cls: "earn-status--over" };
    return { label: "Settled", cls: "earn-status--settled" };
  }

  const scopeLabel = useMemo(() => {
    if (!month || month === "all") return null;
    const opt = (monthOptions || []).find(m => m.value === month);
    return opt ? opt.label.replace(" · this month", "") : month;
  }, [month, monthOptions]);

  if (!performers.length) {
    return (
      <section className="earn-section">
        <header className="earn-header">
          <div className="earn-header-left">
            <h3 className="earn-title">Earnings breakdown</h3>
            {scopeLabel && <span className="earn-scope">{scopeLabel}</span>}
          </div>
          {onAddExpense && (
            <button
              type="button"
              className="cand-btn cand-btn--primary cand-btn--sm earn-add-expense"
              onClick={onAddExpense}
            >
              Add expense
            </button>
          )}
        </header>
        <p className="earn-empty">No handler data for this period.</p>
      </section>
    );
  }

  return (
    <section className="earn-section">
      {/* Header */}
      <header className="earn-header">
        <div className="earn-header-left">
          <h3 className="earn-title">Earnings breakdown</h3>
          {scopeLabel && <span className="earn-scope">{scopeLabel}</span>}
          <p className="earn-sub">
            {performers.length} handler{performers.length !== 1 ? "s" : ""} ·
            Total owed <strong className="earn-green">{fmt(totals.owed)}</strong> ·
            Paid <strong className="earn-red">{fmt(totals.paid)}</strong> ·
            Net <strong className={totals.net > 0 ? "earn-green" : totals.net < 0 ? "earn-red" : "earn-settled"}>{totals.net > 0 ? "Owe " : totals.net < 0 ? "Overpaid " : ""}{fmt(Math.abs(totals.net))}</strong>
          </p>
        </div>
        <div className="earn-header-right">
          {monthOptions && onMonthChange && (
            <label className="earn-filter">
              <span className="earn-filter-label">Month</span>
              <select className="cand-input cand-input--compact" value={month || "all"} onChange={ev => onMonthChange(ev.target.value)}>
                {monthOptions.map(m => <option value={m.value} key={m.value}>{m.label}</option>)}
              </select>
            </label>
          )}
          <label className="earn-filter">
            <span className="earn-filter-label">Sort by</span>
            <select className="cand-input cand-input--compact" value={sortBy} onChange={ev => setSortBy(ev.target.value)}>
              <option value="net_payable">Balance owed</option>
              <option value="auto_earnings_total">Total owed</option>
              <option value="revenue_completed">Revenue</option>
              <option value="commission_total">Commission</option>
              <option value="count">Lead count</option>
            </select>
          </label>
          {onAddExpense && (
            <button
              type="button"
              className="cand-btn cand-btn--primary cand-btn--sm earn-add-expense"
              onClick={onAddExpense}
            >
              Add expense
            </button>
          )}
        </div>
      </header>

      {/* Table */}
      <div className="earn-table-wrap">
        <table className="earn-table">
          <thead>
            <tr>
              <th className="earn-th--name">Handler</th>
              <th className="earn-th--num">Leads</th>
              <th className="earn-th--num">Done</th>
              <th className="earn-th--money">Revenue</th>
              <th className="earn-th--money">Earnings</th>
              <th className="earn-th--money">Salary</th>
              <th className="earn-th--money">Total Owed</th>
              <th className="earn-th--money">Paid Out</th>
              <th className="earn-th--money">Balance</th>
              <th className="earn-th--status">Status</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map(p => {
              const commission = Number(p.commission_total ?? p.auto_earnings_total) || 0;
              const complimentary = Number(p.complimentary_total) || 0;
              const adminComplimentary = Number(p.admin_complimentary_total) || 0;
              const adminComplimentaryCount = Number(p.admin_complimentary_count) || 0;
              const salary = Number(p.salary_total) || 0;
              const owed = Number(p.auto_earnings_total) || 0;
              const recoveries = Number(p.recoveries_total) || 0;
              const paid = Number(p.paid_out_total) || 0;
              const net = Number(p.net_payable) || 0;
              const priorBalance = Number(p.prior_balance) || 0;
              const status = getStatus(net);
              const isExpanded = expanded === p.name;
              const cacheKey = candidateCacheKey(p.name);
              const currentCandidates = handlerCandidates[cacheKey];
              const isLoadingCandidates = loadingCandidates === cacheKey;
              const showOpeningBalance = priorBalance !== 0 && month && month !== "all";
              const signedCurrency = value => {
                const numeric = Number(value) || 0;
                if (numeric > 0) return `+${fmt(numeric)}`;
                if (numeric < 0) return `−${fmt(Math.abs(numeric))}`;
                return fmt(0);
              };
              // Why the opening balance exists. A bare figure invites the
              // question "where did this come from?", so name the months it
              // came from and show the earned/paid/recovered split behind it.
              const priorOwed = Number(p.prior_owed) || 0;
              const priorPaid = Number(p.prior_paid) || 0;
              const priorRecoveries = Number(p.prior_recoveries) || 0;
              const priorMonths = Array.isArray(p.prior_months) ? p.prior_months : [];
              const priorComplimentary = Number(p.prior_complimentary) || 0;
              const priorComplimentaryCount = Number(p.prior_complimentary_count) || 0;
              const priorSpan = monthSpanLabel(priorMonths);
              const whenSuffix = priorSpan ? ` from ${priorSpan}` : " from earlier months";
              // Profile-closure complimentary is granted on a candidate closing,
              // sometimes on another handler's candidate, so "unpaid commission"
              // is the wrong story for it. Name it whenever it is what is owed.
              const balanceIsComplimentary =
                priorBalance > 0 && priorComplimentary > 0 && priorBalance <= priorComplimentary;
              const openingReason = balanceIsComplimentary
                ? `unpaid profile-closure complimentary${whenSuffix}`
                : priorBalance > 0
                  ? `unpaid${whenSuffix}`
                  : `overpaid${priorSpan ? ` in ${priorSpan}` : " in earlier months"}`;
              const openingDetail = [
                `Earned ${fmt(priorOwed)}`,
                priorComplimentary > 0
                  ? `incl. ${fmt(priorComplimentary)} profile-closure complimentary`
                    + (priorComplimentaryCount > 1 ? ` (${priorComplimentaryCount} closures)` : "")
                  : null,
                `paid ${fmt(priorPaid)}`,
                priorRecoveries > 0 ? `recovered ${fmt(priorRecoveries)}` : null,
              ]
                .filter(Boolean)
                .join(" · ")
                + (priorSpan ? ` before ${monthLabel(month)}` : "");

              return (
                <Fragment key={p.ref_key || p.name}>
                  <tr className={`earn-row${isExpanded ? " earn-row--open" : ""}`} onClick={() => toggleExpand(p.name)}>
                    <td className="earn-td--name">
                      <span className="earn-expand-icon">{isExpanded ? "▾" : "▸"}</span>
                      <strong>{p.name}</strong>
                    </td>
                    <td className="earn-td--num">{p.count || 0}</td>
                    <td className="earn-td--num earn-green">{p.completed || 0}</td>
                    <td className="earn-td--money">{fmt(p.revenue_total || 0)}</td>
                    <td className="earn-td--money earn-green">
                      {fmt(commission)}
                      {complimentary > 0 && (
                        <span className="earn-carry-fwd" title="Included completed-profile complimentary amounts">
                          incl. {fmt(complimentary)} complimentary
                        </span>
                      )}
                    </td>
                    <td className="earn-td--money earn-blue">{salary > 0 ? fmt(salary) : "—"}</td>
                    <td className="earn-td--money"><strong>{fmt(owed)}</strong></td>
                    <td className="earn-td--money earn-red">{paid > 0 ? fmt(paid) : "₹0"}</td>
                    <td className={`earn-td--money ${net > 0 ? "earn-green" : net < 0 ? "earn-red" : "earn-settled"}`}>
                      <strong>{net > 0 ? "+" : ""}{fmt(net)}</strong>
                      {priorBalance !== 0 && month && month !== "all" && (
                        <span
                          className="earn-carry-fwd"
                          title={`Carry-forward ${signedCurrency(priorBalance)} — ${openingReason}. ${openingDetail}.`}
                        >
                          {priorBalance > 0 ? "↑" : "↓"}{fmt(Math.abs(priorBalance))} c/f
                        </span>
                      )}
                    </td>
                    <td className="earn-td--status">
                      <span className={`earn-status ${status.cls}`}>{status.label}</span>
                    </td>
                  </tr>
                  {isExpanded && (
                    <tr className="earn-detail-row">
                      <td colSpan={10}>
                        <div className="earn-detail">
                          {isLoadingCandidates && <p className="earn-detail-loading">Loading…</p>}
                          {currentCandidates && (() => {
                            const rows = currentCandidates.filter(c => Number(c.payment) > 0);
                            const pct = (p.commission_pct || 50) / 100;
                            return (
                              <ul className="earn-breakdown-list">
                                {rows.length === 0 && (
                                  <li className="earn-breakdown-item earn-breakdown-empty">
                                    No candidate payments received in this period.
                                  </li>
                                )}
                                {rows.map(c => {
                                  const received = Number(c.payment) || 0;
                                  const referral = Number(c.handler_commission) || Math.round(received * pct);
                                  const date = c.logged_date || c.date || "";
                                  const dateStr = date ? new Date(date).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" }) : "";
                                  const proofs = normalizePaymentProofs(c);
                                  const reportedProofCount = Number(c.proof_count) || 0;
                                  const availableProofCount = proofs.length || reportedProofCount;
                                  return (
                                    <li className="earn-breakdown-item" key={c.id}>
                                      <span className="earn-breakdown-desc">
                                        {c.name} · {fmt(received)} received – {fmt(referral)} referral
                                        {dateStr && <span className="earn-breakdown-date"> · {dateStr}</span>}
                                        {availableProofCount > 0 && onViewPaymentProofs && (
                                          <button
                                            type="button"
                                            className="earn-breakdown-proof-btn"
                                            onClick={(event) => {
                                              event.preventDefault();
                                              event.stopPropagation();
                                              onViewPaymentProofs({
                                                ...c,
                                                id: c.id || c.candidate_id || c.candidateId,
                                                name: c.name || c.candidate_name || "Candidate",
                                                payment_proofs: proofs,
                                              });
                                            }}
                                            title={
                                              availableProofCount === 1
                                                ? "View payment proof"
                                                : `View ${availableProofCount} payment proofs`
                                            }
                                            aria-label={`View payment proofs for ${c.name || c.candidate_name || "candidate"}`}
                                          >
                                            📷
                                          </button>
                                        )}
                                      </span>
                                      <strong className="earn-breakdown-amount">{fmt(referral)}</strong>
                                    </li>
                                  );
                                })}
                                {adminComplimentary > 0 && (
                                  <li className="earn-breakdown-item">
                                    <span className="earn-breakdown-desc">
                                      Admin complimentary · {adminComplimentaryCount} completed profile{adminComplimentaryCount === 1 ? "" : "s"}
                                    </span>
                                    <strong className="earn-breakdown-amount">{fmt(adminComplimentary)}</strong>
                                  </li>
                                )}
                                <li className="earn-breakdown-item earn-breakdown-total">
                                  <span className="earn-breakdown-total-title">
                                    <strong>Total ({Number(p.count) || rows.length} candidates)</strong>
                                  </span>
                                  <span className="earn-breakdown-summary">
                                    {showOpeningBalance && (
                                      <span className="earn-summary-metric earn-summary-opening">
                                        <span className="earn-summary-label">Opening balance</span>
                                        <strong>{signedCurrency(priorBalance)}</strong>
                                        <span
                                          className={`earn-summary-note${balanceIsComplimentary ? " earn-summary-note--complimentary" : ""}`}
                                          title={openingDetail}
                                        >
                                          {openingReason}
                                        </span>
                                      </span>
                                    )}
                                    {/* Earnings is the full amount owed for the month —
                                        commission AND salary. Showing commission alone
                                        made the strip contradict itself: the numbers no
                                        longer added up to the closing balance beside them. */}
                                    <span className="earn-summary-metric earn-summary-earnings">
                                      <span className="earn-summary-label">Earnings</span>
                                      <strong>{fmt(owed)}</strong>
                                      {salary > 0 && (
                                        <span className="earn-summary-note" title="Monthly salary included in this month's earnings">
                                          incl. {fmt(salary)} salary
                                        </span>
                                      )}
                                    </span>
                                    {recoveries > 0 && (
                                      <span className="earn-summary-metric earn-summary-recoveries">
                                        <span className="earn-summary-label">Recoveries</span>
                                        <strong>−{fmt(recoveries)}</strong>
                                      </span>
                                    )}
                                    <span className="earn-summary-metric earn-summary-expenses">
                                      <span className="earn-summary-label">Expenses</span>
                                      <strong>{paid > 0 ? `−${fmt(paid)}` : fmt(0)}</strong>
                                    </span>
                                    <span className={`earn-summary-metric earn-summary-balance ${net > 0 ? "earn-summary-balance--positive" : net < 0 ? "earn-summary-balance--negative" : "earn-summary-balance--zero"}`}>
                                      <span className="earn-summary-label">{showOpeningBalance ? "Closing balance" : "Net balance"}</span>
                                      <strong>{signedCurrency(net)}</strong>
                                      <span className={`earn-status ${status.cls}`}>{status.label}</span>
                                    </span>
                                  </span>
                                </li>
                              </ul>
                            );
                          })()}
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
          <tfoot>
            <tr className="earn-foot">
              <td><strong>Totals</strong></td>
              <td className="earn-td--num">{performers.reduce((s, p) => s + (p.count || 0), 0)}</td>
              <td className="earn-td--num">{performers.reduce((s, p) => s + (p.completed || 0), 0)}</td>
              <td className="earn-td--money">{fmt(performers.reduce((s, p) => s + (Number(p.revenue_total) || 0), 0))}</td>
              <td className="earn-td--money">{fmt(totals.commission)}</td>
              <td className="earn-td--money">{fmt(totals.salary)}</td>
              <td className="earn-td--money"><strong>{fmt(totals.owed)}</strong></td>
              <td className="earn-td--money">{fmt(totals.paid)}</td>
              <td className={`earn-td--money ${totals.net > 0 ? "earn-green" : totals.net < 0 ? "earn-red" : "earn-settled"}`}><strong>{fmt(totals.net)}</strong></td>
              <td></td>
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  );
}
