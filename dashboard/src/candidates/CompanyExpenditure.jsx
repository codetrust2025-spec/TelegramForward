import { useState, useEffect, useMemo, useCallback, Fragment } from "react";
import "./CompanyExpenditure.css";

const CATEGORIES = [
  { value: "rent", label: "Rent / space" },
  { value: "tools", label: "Tools / equipment" },
  { value: "marketing", label: "Marketing / ads" },
  { value: "salary_staff", label: "Staff salary" },
  { value: "travel", label: "Travel / fuel" },
  { value: "internet", label: "Internet / telecom" },
  { value: "office", label: "Office supplies" },
  { value: "subscription", label: "Subscriptions / SaaS" },
  { value: "other", label: "Other" },
];

const ROWS_PER_PAGE = 8;

function fmt(v) {
  const n = Number(v) || 0;
  if (n === 0) return "₹0";
  return `₹${n.toLocaleString("en-IN")}`;
}

function fmtDate(d) {
  if (!d) return "—";
  try {
    return new Date(d).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
  } catch { return d; }
}

export default function CompanyExpenditure({ onClose, apiBase = "" }) {
  const [expenses, setExpenses] = useState([]);
  const [months, setMonths] = useState([]);
  const [totals, setTotals] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filterMonth, setFilterMonth] = useState("all");
  const [filterCat, setFilterCat] = useState("all");
  const [editId, setEditId] = useState(null);
  const [form, setForm] = useState({
    title: "", amount: "", category: "other", note: "",
    date: new Date().toISOString().slice(0, 10), recurring: false,
  });
  const [saving, setSaving] = useState(false);
  const [page, setPage] = useState(0);
  const [tab, setTab] = useState("overview"); // overview | company | handler

  // Fetch company expenses
  const fetchExpenses = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (filterMonth !== "all") params.set("month", filterMonth);
      const [expRes, totalRes] = await Promise.all([
        fetch(`${apiBase}/company-expenses?${params.toString()}`).then(r => r.json()),
        fetch(`${apiBase}/company-expenses/total?${params.toString()}`).then(r => r.json()),
      ]);
      if (expRes.status === "ok") {
        setExpenses(expRes.expenses || []);
        setMonths(expRes.available_months || []);
      }
      if (totalRes.status === "ok") {
        setTotals(totalRes);
      }
    } catch (e) {
      setError(e.message || "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [filterMonth, apiBase]);

  useEffect(() => { fetchExpenses(); }, [fetchExpenses]);

  useEffect(() => {
    const handler = (ev) => { if (ev.key === "Escape") onClose?.(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  // Filtered list
  const filtered = useMemo(() => {
    let list = expenses;
    if (filterCat !== "all") list = list.filter(r => r.category === filterCat);
    return list;
  }, [expenses, filterCat]);

  // Pagination
  const totalPages = Math.max(1, Math.ceil(filtered.length / ROWS_PER_PAGE));
  const pagedRows = filtered.slice(page * ROWS_PER_PAGE, (page + 1) * ROWS_PER_PAGE);
  useEffect(() => { setPage(0); }, [filterMonth, filterCat]);

  // Month options
  const monthOptions = useMemo(() => [
    { value: "all", label: "All time" },
    ...months.map(m => ({ value: m.value, label: m.label })),
  ], [months]);

  // Form
  function resetForm() {
    setEditId(null);
    setForm({ title: "", amount: "", category: "other", note: "", date: new Date().toISOString().slice(0, 10), recurring: false });
  }

  function startEdit(row) {
    setEditId(row.id);
    setForm({ title: row.title || "", amount: String(row.amount || ""), category: row.category || "other", note: row.note || "", date: row.date || new Date().toISOString().slice(0, 10), recurring: !!row.recurring });
  }

  async function handleSubmit(ev) {
    ev?.preventDefault?.();
    if (!form.title.trim()) { setError("Title is required"); return; }
    const amt = Number(form.amount);
    if (!Number.isFinite(amt) || amt <= 0) { setError("Amount must be > 0"); return; }
    setSaving(true); setError("");
    try {
      const payload = { title: form.title.trim(), amount: amt, category: form.category, note: form.note.trim(), date: form.date, recurring: form.recurring };
      let res;
      if (editId) {
        res = await (await fetch(`${apiBase}/company-expenses/${editId}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) })).json();
      } else {
        res = await (await fetch(`${apiBase}/company-expenses`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) })).json();
      }
      if (res.status !== "ok") { setError(res.message || "Save failed"); return; }
      resetForm();
      fetchExpenses();
    } catch (e) { setError(e.message || "Network error"); }
    finally { setSaving(false); }
  }

  async function handleDelete(row) {
    if (!window.confirm(`Delete "${row.title}" (${fmt(row.amount)})?`)) return;
    try {
      const res = await (await fetch(`${apiBase}/company-expenses/${row.id}`, { method: "DELETE" })).json();
      if (res.status === "ok") fetchExpenses();
      else setError(res.message || "Delete failed");
    } catch (e) { setError(e.message || "Network error"); }
  }

  // Category breakdown for chart
  const categoryBreakdown = useMemo(() => {
    if (!totals) return [];
    const byCat = totals.company_expenses?.by_category || {};
    return Object.entries(byCat)
      .map(([k, v]) => ({ key: k, label: CATEGORIES.find(c => c.value === k)?.label || k, amount: v }))
      .sort((a, b) => b.amount - a.amount);
  }, [totals]);

  return (
    <div className="cand-modal-backdrop" onClick={ev => ev.target === ev.currentTarget && onClose?.()}>
      <div className="compexp-modal">
        {/* Header */}
        <header className="compexp-header">
          <div className="compexp-header-left">
            <h3 className="compexp-title">Total Expenditure</h3>
            <p className="compexp-sub">Company-wide spending — handler payouts + operational costs</p>
          </div>
          <button type="button" className="cand-modal-close" onClick={onClose} aria-label="Close">×</button>
        </header>

        {/* Summary cards */}
        {totals && (
          <div className="compexp-summary">
            <div className="compexp-card compexp-card--grand">
              <span className="compexp-card-label">Grand Total</span>
              <span className="compexp-card-value">{fmt(totals.grand_total)}</span>
            </div>
            <div className="compexp-card compexp-card--handler">
              <span className="compexp-card-label">Handler Payouts</span>
              <span className="compexp-card-value">{fmt(totals.handler_payouts?.total)}</span>
              <span className="compexp-card-count">{totals.handler_payouts?.count || 0} entries</span>
            </div>
            <div className="compexp-card compexp-card--company">
              <span className="compexp-card-label">Company Expenses</span>
              <span className="compexp-card-value">{fmt(totals.company_expenses?.total)}</span>
              <span className="compexp-card-count">{totals.company_expenses?.count || 0} entries</span>
            </div>
          </div>
        )}

        {/* Tabs */}
        <nav className="compexp-tabs">
          <button type="button" className={`compexp-tab${tab === "overview" ? " compexp-tab--active" : ""}`} onClick={() => setTab("overview")}>Overview</button>
          <button type="button" className={`compexp-tab${tab === "company" ? " compexp-tab--active" : ""}`} onClick={() => setTab("company")}>Company Expenses</button>
          <div className="compexp-tabs-right">
            <select className="cand-input cand-input--compact" value={filterMonth} onChange={ev => setFilterMonth(ev.target.value)}>
              {monthOptions.map(m => <option value={m.value} key={m.value}>{m.label}</option>)}
            </select>
          </div>
        </nav>

        {/* Overview tab */}
        {tab === "overview" && totals && (
          <div className="compexp-overview">
            {categoryBreakdown.length > 0 ? (
              <div className="compexp-breakdown">
                <h4 className="compexp-breakdown-title">Company expenses by category</h4>
                <div className="compexp-breakdown-bars">
                  {categoryBreakdown.map(item => {
                    const max = categoryBreakdown[0]?.amount || 1;
                    const pct = Math.max(4, (item.amount / max) * 100);
                    return (
                      <div className="compexp-bar-row" key={item.key}>
                        <span className="compexp-bar-label">{item.label}</span>
                        <div className="compexp-bar-track">
                          <div className="compexp-bar-fill" style={{ width: `${pct}%` }} />
                        </div>
                        <span className="compexp-bar-value">{fmt(item.amount)}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : (
              <p className="compexp-empty">No company expenses logged yet. Switch to "Company Expenses" tab to add one.</p>
            )}
            {totals.grand_total > 0 && (
              <div className="compexp-split-chart">
                <h4 className="compexp-breakdown-title">Expenditure split</h4>
                <div className="compexp-split-bars">
                  <div className="compexp-split-item">
                    <span className="compexp-split-label">Handler payouts</span>
                    <div className="compexp-split-track">
                      <div className="compexp-split-fill compexp-split-fill--handler" style={{ width: `${((totals.handler_payouts?.total || 0) / totals.grand_total) * 100}%` }} />
                    </div>
                    <span className="compexp-split-value">{fmt(totals.handler_payouts?.total)} ({Math.round(((totals.handler_payouts?.total || 0) / totals.grand_total) * 100)}%)</span>
                  </div>
                  <div className="compexp-split-item">
                    <span className="compexp-split-label">Company ops</span>
                    <div className="compexp-split-track">
                      <div className="compexp-split-fill compexp-split-fill--company" style={{ width: `${((totals.company_expenses?.total || 0) / totals.grand_total) * 100}%` }} />
                    </div>
                    <span className="compexp-split-value">{fmt(totals.company_expenses?.total)} ({Math.round(((totals.company_expenses?.total || 0) / totals.grand_total) * 100)}%)</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Company Expenses tab */}
        {tab === "company" && (
          <div className="compexp-company">
            {/* Add/edit form */}
            <form className="compexp-form" onSubmit={handleSubmit}>
              <div className="compexp-form-row">
                <label className="compexp-field compexp-field--title">
                  <span className="cand-field-label">Title *</span>
                  <input className="cand-input" value={form.title} onChange={ev => setForm(f => ({ ...f, title: ev.target.value }))} placeholder="e.g. Office rent July" required />
                </label>
                <label className="compexp-field compexp-field--amount">
                  <span className="cand-field-label">Amount (₹) *</span>
                  <input className="cand-input" type="number" min="0" step="100" value={form.amount} onChange={ev => setForm(f => ({ ...f, amount: ev.target.value }))} placeholder="5000" required />
                </label>
                <label className="compexp-field compexp-field--cat">
                  <span className="cand-field-label">Category</span>
                  <select className="cand-input" value={form.category} onChange={ev => setForm(f => ({ ...f, category: ev.target.value }))}>
                    {CATEGORIES.map(c => <option value={c.value} key={c.value}>{c.label}</option>)}
                  </select>
                </label>
                <label className="compexp-field compexp-field--date">
                  <span className="cand-field-label">Date</span>
                  <input className="cand-input" type="date" value={form.date} onChange={ev => setForm(f => ({ ...f, date: ev.target.value }))} />
                </label>
              </div>
              <div className="compexp-form-row2">
                <label className="compexp-field compexp-field--note">
                  <span className="cand-field-label">Note</span>
                  <input className="cand-input" value={form.note} onChange={ev => setForm(f => ({ ...f, note: ev.target.value }))} placeholder="Optional description" />
                </label>
                <div className="compexp-form-actions">
                  {editId && <button type="button" className="cand-btn cand-btn--ghost" onClick={resetForm}>Cancel</button>}
                  <button type="submit" className="cand-btn cand-btn--primary" disabled={saving}>{saving ? "Saving…" : editId ? "Update" : "+ Add expense"}</button>
                </div>
              </div>
            </form>

            {error && <div className="cand-modal-error">{error}</div>}

            {/* Filter */}
            <div className="compexp-filter-row">
              <select className="cand-input cand-input--compact" value={filterCat} onChange={ev => setFilterCat(ev.target.value)}>
                <option value="all">All categories</option>
                {CATEGORIES.map(c => <option value={c.value} key={c.value}>{c.label}</option>)}
              </select>
              <span className="compexp-count">{filtered.length} expense{filtered.length !== 1 ? "s" : ""} · Total: {fmt(filtered.reduce((s, r) => s + (Number(r.amount) || 0), 0))}</span>
            </div>

            {/* Table */}
            {loading ? <p className="compexp-empty">Loading…</p> : filtered.length === 0 ? (
              <p className="compexp-empty">No company expenses logged{filterMonth !== "all" ? " for this period" : ""}.</p>
            ) : (
              <div className="compexp-table-wrap">
                <table className="compexp-table">
                  <thead>
                    <tr>
                      <th>Title</th>
                      <th>Amount</th>
                      <th>Category</th>
                      <th>Date</th>
                      <th>Note</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pagedRows.map(row => (
                      <tr className={editId === row.id ? "compexp-row--editing" : ""} key={row.id}>
                        <td className="compexp-td--title">{row.title || "—"}</td>
                        <td className="compexp-td--amount">{fmt(row.amount)}</td>
                        <td><span className={`compexp-cat compexp-cat--${row.category}`}>{CATEGORIES.find(c => c.value === row.category)?.label || row.category}</span></td>
                        <td className="compexp-td--date">{fmtDate(row.date)}</td>
                        <td className="compexp-td--note">{row.note || "—"}</td>
                        <td className="compexp-td--actions">
                          <button type="button" className="cand-btn cand-btn--ghost cand-btn--xs" onClick={() => startEdit(row)} title="Edit">✎</button>
                          <button type="button" className="cand-btn cand-btn--ghost cand-btn--xs cand-btn--danger-ghost" onClick={() => handleDelete(row)} title="Delete">🗑</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="compexp-pagination">
                <button type="button" className="cand-btn cand-btn--ghost cand-btn--xs" disabled={page === 0} onClick={() => setPage(p => p - 1)}>← Prev</button>
                <span>Page {page + 1} of {totalPages}</span>
                <button type="button" className="cand-btn cand-btn--ghost cand-btn--xs" disabled={page >= totalPages - 1} onClick={() => setPage(p => p + 1)}>Next →</button>
              </div>
            )}
          </div>
        )}

        {/* Footer */}
        <footer className="compexp-footer">
          <button type="button" className="cand-btn cand-btn--ghost" onClick={onClose}>Close</button>
        </footer>
      </div>
    </div>
  );
}
