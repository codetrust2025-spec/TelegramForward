import { useState, useMemo, Fragment } from "react";
import "./EarningsBreakdown.css";

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
  onEditPayout,
  handlerView = false,
  handlerName = null,
  formatCurrency,
  apiBase = "",
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

  // Fetch candidates for a specific handler when expanded
  async function toggleExpand(name) {
    if (expanded === name) { setExpanded(null); return; }
    setExpanded(name);
    if (handlerCandidates[name]) return; // already loaded
    setLoadingCandidates(name);
    try {
      const params = new URLSearchParams();
      if (month && month !== "all") params.set("month", month);
      params.set("reference", name);
      const res = await (await fetch(`${apiBase}/candidates?${params.toString()}`, { credentials: "include" })).json();
      if (res.status === "ok") {
        setHandlerCandidates(prev => ({ ...prev, [name]: res.candidates || [] }));
      }
    } catch (e) { /* silent */ }
    finally { setLoadingCandidates(null); }
  }

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
          <h3 className="earn-title">Earnings breakdown</h3>
          {scopeLabel && <span className="earn-scope">{scopeLabel}</span>}
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
              <th className="earn-th--money">Commission (50%)</th>
              <th className="earn-th--money">Salary</th>
              <th className="earn-th--money">Total Owed</th>
              <th className="earn-th--money">Paid Out</th>
              <th className="earn-th--money">Balance</th>
              <th className="earn-th--status">Status</th>
              <th className="earn-th--action"></th>
            </tr>
          </thead>
          <tbody>
            {sorted.map(p => {
              const commission = Number(p.commission_total ?? p.auto_earnings_total) || 0;
              const salary = Number(p.salary_total) || 0;
              const owed = Number(p.auto_earnings_total) || 0;
              const paid = Number(p.paid_out_total) || 0;
              const net = Number(p.net_payable) || 0;
              const status = getStatus(net);
              const isExpanded = expanded === p.name;

              return (
                <Fragment key={p.ref_key || p.name}>
                  <tr className={`earn-row${isExpanded ? " earn-row--open" : ""}`} onClick={() => toggleExpand(p.name)}>
                    <td className="earn-td--name">
                      <span className="earn-expand-icon">{isExpanded ? "▾" : "▸"}</span>
                      <strong>{p.name}</strong>
                    </td>
                    <td className="earn-td--num">{p.count || 0}</td>
                    <td className="earn-td--num earn-green">{p.completed || 0}</td>
                    <td className="earn-td--money">{fmt(p.revenue_completed || 0)}</td>
                    <td className="earn-td--money earn-green">{fmt(commission)}</td>
                    <td className="earn-td--money earn-blue">{salary > 0 ? fmt(salary) : "—"}</td>
                    <td className="earn-td--money"><strong>{fmt(owed)}</strong></td>
                    <td className="earn-td--money earn-red">{paid > 0 ? fmt(paid) : "₹0"}</td>
                    <td className={`earn-td--money ${net > 0 ? "earn-green" : net < 0 ? "earn-red" : "earn-settled"}`}>
                      <strong>{net > 0 ? "+" : ""}{fmt(net)}</strong>
                    </td>
                    <td className="earn-td--status">
                      <span className={`earn-status ${status.cls}`}>{status.label}</span>
                    </td>
                    <td className="earn-td--action">
                      {onEditPayout && <button type="button" className="cand-btn cand-btn--ghost cand-btn--xs" onClick={ev => { ev.stopPropagation(); onEditPayout(p); }} title="Manage payouts">Edit payouts</button>}
                    </td>
                  </tr>
                  {isExpanded && (
                    <tr className="earn-detail-row">
                      <td colSpan={11}>
                        <div className="earn-detail">
                          <p className="earn-detail-formula">
                            Owed = Commission ({fmt(commission)}) + Salary ({fmt(salary)}) = <strong>{fmt(owed)}</strong> — Paid out ({fmt(paid)}) = <strong className={net > 0 ? "earn-green" : net < 0 ? "earn-red" : "earn-settled"}>Net {net >= 0 ? fmt(net) : `-${fmt(Math.abs(net))}`}</strong>
                          </p>
                          {loadingCandidates === p.name && <p className="earn-detail-loading">Loading candidates…</p>}
                          {handlerCandidates[p.name] && (
                            <div className="earn-candidates-wrap">
                              <p className="earn-detail-label" style={{ margin: "8px 0 6px" }}>Commission breakdown — {p.commission_pct || 50}% of each client payment:</p>
                              <table className="earn-candidates-table">
                                <thead><tr>
                                  <th>Candidate</th>
                                  <th>Technology</th>
                                  <th>Stage</th>
                                  <th style={{ textAlign: "right" }}>Client paid</th>
                                  <th style={{ textAlign: "right" }}>{p.commission_pct || 50}% commission</th>
                                </tr></thead>
                                <tbody>
                                  {handlerCandidates[p.name].filter(c => Number(c.amount_received) > 0 || c.stage === "completed").map(c => {
                                    const clientPaid = Number(c.amount_received) || 0;
                                    const commShare = Math.round(clientPaid * ((p.commission_pct || 50) / 100));
                                    return (
                                      <tr key={c.id}>
                                        <td><strong>{c.name}</strong></td>
                                        <td>{c.technology || "—"}</td>
                                        <td><span className={`cand-badge ${c.stage === "completed" ? "cand-badge--good" : "cand-badge--info"}`}>{c.stage || "—"}</span></td>
                                        <td style={{ textAlign: "right" }}>{fmt(clientPaid)}</td>
                                        <td style={{ textAlign: "right" }} className="earn-green"><strong>{fmt(commShare)}</strong></td>
                                      </tr>
                                    );
                                  })}
                                  {handlerCandidates[p.name].filter(c => Number(c.amount_received) > 0 || c.stage === "completed").length === 0 && (
                                    <tr><td colSpan={5} className="earn-empty" style={{ padding: 10 }}>No payments received yet for this handler's candidates.</td></tr>
                                  )}
                                </tbody>
                              </table>
                            </div>
                          )}
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
              <td className="earn-td--money">{fmt(performers.reduce((s, p) => s + (Number(p.revenue_completed) || 0), 0))}</td>
              <td className="earn-td--money">{fmt(totals.commission)}</td>
              <td className="earn-td--money">{fmt(totals.salary)}</td>
              <td className="earn-td--money"><strong>{fmt(totals.owed)}</strong></td>
              <td className="earn-td--money">{fmt(totals.paid)}</td>
              <td className={`earn-td--money ${totals.net > 0 ? "earn-green" : totals.net < 0 ? "earn-red" : "earn-settled"}`}><strong>{fmt(totals.net)}</strong></td>
              <td></td>
              <td></td>
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  );
}
