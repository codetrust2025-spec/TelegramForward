import { useState, useEffect, useCallback, useMemo, useRef, Fragment } from "react";

/**
 * Manage handler payouts — redesigned wide modal.
 * Two-column top row (form | filters), full-width paginated table below.
 * No internal scrolling on desktop.
 */

const ROWS_PER_PAGE = 7;

export default function PayoutModal({
  handlerNames = [],
  ownedSummary,
  onClose,
  onChanged,
  // injected from parent so we don't re-import
  apiBase,
  categories,
  categoryLabels,
  formatCurrency,
  formatDate,
}) {
  const ve = apiBase;
  const B0 = categories;
  const Ex = categoryLabels;
  const Jc = formatCurrency;
  const rR = formatDate;

  const [entries, setEntries] = useState([]);
  const [months, setMonths] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filterHandler, setFilterHandler] = useState("all");
  const [filterMonth, setFilterMonth] = useState("all");
  const [filterCat, setFilterCat] = useState("all");
  const [editId, setEditId] = useState(null);
  const [form, setForm] = useState(() => ({
    reference: handlerNames[0] || "",
    amount: "",
    category: "commission",
    note: "",
    date: new Date().toISOString().slice(0, 10),
  }));
  const [saving, setSaving] = useState(false);
  const [proofFile, setProofFile] = useState(null);
  const proofInputRef = useRef(null);
  const [previewProof, setPreviewProof] = useState(null);
  const [page, setPage] = useState(0);

  // ── Data fetching ──
  const fetchData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (filterMonth !== "all") params.set("month", filterMonth);
      const res = await (await fetch(`${ve}/handler-expenses?${params.toString()}`)).json();
      if (res.status === "ok") {
        setEntries(res.expenses || []);
        setMonths(res.available_months || []);
      } else {
        setError(res.message || "Failed to load");
      }
    } catch (err) {
      setError(err.message || "Network error");
    } finally {
      setLoading(false);
    }
  }, [filterMonth, ve]);

  useEffect(() => { fetchData(); }, [fetchData]);

  useEffect(() => {
    const handler = (ev) => { if (ev.key === "Escape" && !editId) onClose?.(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose, editId]);

  // ── Derived data ──
  const filtered = useMemo(() => {
    let list = entries;
    if (filterHandler !== "all") {
      const lc = filterHandler.toLowerCase();
      list = list.filter(r => (r.reference || "").toLowerCase() === lc);
    }
    if (filterCat !== "all") list = list.filter(r => r.category === filterCat);
    return list;
  }, [entries, filterHandler, filterCat]);

  const owed = Number(ownedSummary?.owed) || 0;
  const paidOut = useMemo(() => filtered.reduce((s, r) => s + (Number(r.amount) || 0), 0), [filtered]);
  const balance = owed - paidOut;

  const allHandlers = useMemo(() => {
    const map = new Map();
    handlerNames.forEach(n => map.set(n.toLowerCase(), n));
    entries.forEach(r => { const n = (r.reference || "").trim(); if (n) map.set(n.toLowerCase(), n); });
    return [...map.values()].sort((a, b) => a.localeCompare(b));
  }, [entries, handlerNames]);

  const monthOptions = useMemo(() => [
    { value: "all", label: "All time" },
    ...months.map(m => ({ value: m.value, label: m.is_current ? `${m.label} · this month` : m.label }))
  ], [months]);

  // ── Pagination ──
  const totalPages = Math.max(1, Math.ceil(filtered.length / ROWS_PER_PAGE));
  const pagedRows = filtered.slice(page * ROWS_PER_PAGE, (page + 1) * ROWS_PER_PAGE);
  // Reset page when filters change
  useEffect(() => { setPage(0); }, [filterHandler, filterMonth, filterCat]);

  // ── Form helpers ──
  function resetForm() {
    setEditId(null);
    setProofFile(null);
    if (proofInputRef.current) proofInputRef.current.value = "";
    setForm({
      reference: filterHandler !== "all" ? filterHandler : allHandlers[0] || "",
      amount: "",
      category: "commission",
      note: "",
      date: new Date().toISOString().slice(0, 10),
    });
  }

  function startEdit(row) {
    setEditId(row.id);
    setForm({
      reference: row.reference || "",
      amount: String(row.amount || ""),
      category: row.category || "other",
      note: row.note || "",
      date: row.date || new Date().toISOString().slice(0, 10),
    });
  }

  async function handleSubmit(ev) {
    ev?.preventDefault?.();
    if (!form.reference.trim()) { setError("Handler name is required"); return; }
    const amt = Number(form.amount);
    if (!Number.isFinite(amt) || amt <= 0) { setError("Amount must be greater than zero"); return; }
    if (!editId && !proofFile) { setError("Payment screenshot is required"); return; }
    setSaving(true);
    setError("");
    try {
      let res;
      if (editId) {
        res = await (await fetch(`${ve}/handler-expenses/${editId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ reference: form.reference.trim(), amount: amt, category: form.category, note: form.note.trim(), date: form.date }),
        })).json();
      } else {
        const fd = new FormData();
        fd.append("reference", form.reference.trim());
        fd.append("amount", String(amt));
        fd.append("category", form.category);
        fd.append("note", form.note.trim());
        fd.append("date", form.date);
        fd.append("file", proofFile);
        res = await (await fetch(`${ve}/handler-expenses`, { method: "POST", body: fd })).json();
      }
      if (res.status !== "ok") { setError(res.message || "Save failed"); return; }
      resetForm();
      fetchData();
      onChanged?.();
    } catch (err) { setError(err.message || "Network error"); }
    finally { setSaving(false); }
  }

  async function handleDelete(row) {
    const catLabel = Ex[row.category] || row.category || "payout";
    if (!window.confirm(`Delete this ₹${row.amount.toLocaleString("en-IN")} ${catLabel} for ${row.reference}?`)) return;
    try {
      const res = await (await fetch(`${ve}/handler-expenses/${row.id}`, { method: "DELETE" })).json();
      if (res.status === "ok") { fetchData(); onChanged?.(); }
      else setError(res.message || "Delete failed");
    } catch (err) { setError(err.message || "Network error"); }
  }

  function clearFilters() { setFilterHandler("all"); setFilterMonth("all"); setFilterCat("all"); }
  const filtersActive = filterHandler !== "all" || filterMonth !== "all" || filterCat !== "all";

  // ── Render ──
  return <Fragment>
    <div className="cand-modal-backdrop" onClick={ev => ev.target === ev.currentTarget && onClose?.()}>
      <div className="payout-modal">
        {/* ─── HEADER ─── */}
        <header className="payout-modal__header">
          <h3 className="payout-modal__title">Manage handler payouts</h3>
          <span className="cand-payout-chunk"><strong>{filtered.length}</strong> entr{filtered.length === 1 ? "y" : "ies"}</span>
          <span className="cand-payout-chunk cand-payout-chunk--earn" title="Auto-computed: 50% with shortfall penalty"><span className="cand-payout-pip" /> Owed (50%) <strong>{Jc(owed)}</strong></span>
          <span className="cand-payout-chunk cand-payout-chunk--ded"><span className="cand-payout-pip" /> Paid out <strong>{Jc(paidOut)}</strong></span>
          <span className={`cand-payout-chunk ${balance > 0 ? "cand-payout-chunk--net-pos" : balance === 0 ? "cand-payout-chunk--net-zero" : "cand-payout-chunk--net-neg"}`}>
            <span className="cand-payout-pip" />{balance > 0 ? "Still owe " : balance === 0 ? "Settled " : "Overpaid by "}<strong>{Jc(Math.abs(balance))}</strong>
          </span>
          {filtersActive && <button type="button" className="cand-btn cand-btn--ghost cand-btn--xs" onClick={clearFilters}>Clear filters</button>}
          <button type="button" className="cand-modal-close" onClick={onClose} aria-label="Close">×</button>
        </header>

        {/* ─── TWO-COLUMN ROW: form left | filters right ─── */}
        <div className="payout-modal__top-row">
          {/* LEFT: Payout entry form */}
          <form className="payout-modal__form" onSubmit={handleSubmit}>
            <div className="payout-modal__form-grid">
              <label className="payout-modal__field">
                <span className="cand-field-label">Handler *</span>
                <input className="cand-input payout-modal__input" value={form.reference} onChange={ev => setForm(f => ({ ...f, reference: ev.target.value }))} placeholder="e.g. Thrilok" list="payout-ref-list" required />
                <datalist id="payout-ref-list">{allHandlers.map(n => <option value={n} key={n} />)}</datalist>
              </label>
              <label className="payout-modal__field">
                <span className="cand-field-label">Amount (₹) * <span className="cand-exp-kind-tag cand-exp-kind-tag--payout">subtracted from what's owed</span></span>
                <input className="cand-input payout-modal__input" type="number" min="0" step="100" value={form.amount} onChange={ev => setForm(f => ({ ...f, amount: ev.target.value }))} placeholder="5000" required />
              </label>
              <label className="payout-modal__field">
                <span className="cand-field-label">Category</span>
                <select className="cand-input payout-modal__input" value={form.category} onChange={ev => setForm(f => ({ ...f, category: ev.target.value }))}>{B0.map(c => <option value={c.value} key={c.value}>{c.label}</option>)}</select>
              </label>
              <label className="payout-modal__field">
                <span className="cand-field-label">Date</span>
                <input className="cand-input payout-modal__input" type="date" value={form.date} onChange={ev => setForm(f => ({ ...f, date: ev.target.value }))} />
              </label>
              <label className="payout-modal__field payout-modal__field--wide">
                <span className="cand-field-label">Note</span>
                <input className="cand-input payout-modal__input" value={form.note} onChange={ev => setForm(f => ({ ...f, note: ev.target.value }))} placeholder="e.g. May commission · taxi to client meeting" />
              </label>
            </div>
            <div className="payout-modal__form-actions">
              {!editId && <div className={`cand-payout-attach${proofFile ? " cand-payout-attach--done" : ""}`} onClick={() => proofInputRef.current?.click()} role="button" tabIndex={0} title={proofFile ? proofFile.name : "Attach payment screenshot (required)"}>
                <input ref={proofInputRef} type="file" accept="image/*" onChange={ev => { const file = ev.target.files?.[0]; if (file) { if (!/^image\//.test(file.type || "")) { setError("Only image files allowed"); return; } if (file.size > 8 * 1024 * 1024) { setError("File too large (max 8 MB)"); return; } setProofFile(file); setError(""); } }} hidden />
                <span className="cand-payout-attach-icon">{proofFile ? "✓" : "📷"}</span>
                <span className="cand-payout-attach-text">{proofFile ? proofFile.name.slice(0, 20) : "Attach screenshot *"}</span>
              </div>}
              {editId && <button type="button" className="cand-btn cand-btn--ghost" onClick={resetForm}>Cancel edit</button>}
              <button type="submit" className="cand-btn cand-btn--primary" disabled={saving || (!editId && !proofFile)}>{saving ? "Saving…" : editId ? "Save changes" : "+ Log payout"}</button>
            </div>
            {error && <div className="cand-modal-error" style={{ marginTop: 6 }}>{error}</div>}
          </form>

          {/* RIGHT: Filters */}
          <div className="payout-modal__filters">
            <label className="payout-modal__filter-field">
              <span className="cand-field-label">Period</span>
              <select className="cand-input payout-modal__input" value={filterMonth} onChange={ev => setFilterMonth(ev.target.value)}>{monthOptions.map(m => <option value={m.value} key={m.value}>{m.label}</option>)}</select>
            </label>
            <label className="payout-modal__filter-field">
              <span className="cand-field-label">Category</span>
              <select className="cand-input payout-modal__input" value={filterCat} onChange={ev => setFilterCat(ev.target.value)}>
                <option value="all">All categories</option>
                {B0.map(c => <option value={c.value} key={c.value}>{c.label}</option>)}
              </select>
            </label>
          </div>
        </div>

        {/* ─── TABLE ─── */}
        <div className="payout-modal__table-area">
          {loading ? <div className="cand-exp-empty">Loading…</div> : filtered.length === 0 ? (
            <div className="cand-exp-empty">No entries match filters. <button type="button" className="cand-link" onClick={clearFilters}>Clear filters</button></div>
          ) : (
            <table className="payout-modal__table">
              <thead><tr>
                <th className="payout-col--handler">Handler</th>
                <th className="payout-col--amount">Amount</th>
                <th className="payout-col--cat">Category</th>
                <th className="payout-col--date">Date</th>
                <th className="payout-col--note">Note</th>
                <th className="payout-col--proof">Proof</th>
                <th className="payout-col--actions">Actions</th>
              </tr></thead>
              <tbody>
                {pagedRows.map(row => (
                  <tr className={`payout-modal__row${editId === row.id ? " payout-modal__row--editing" : ""}`} key={row.id}>
                    <td className="payout-col--handler">{row.reference}</td>
                    <td className="payout-col--amount">−{Jc(row.amount)}</td>
                    <td className="payout-col--cat"><span className={`cand-exp-cat cand-exp-cat--${row.category}`}>{Ex[row.category] || row.category}</span></td>
                    <td className="payout-col--date">{rR(row.date)}</td>
                    <td className="payout-col--note">{row.note || <em>—</em>}</td>
                    <td className="payout-col--proof">
                      {(row.proofs?.length > 0) ? <button type="button" className="cand-proof-thumb-btn" onClick={() => setPreviewProof(row.proofs[0])} title="View proof"><img src={`${ve}${row.proofs[0].url}`} alt="proof" className="cand-proof-thumb-img" loading="lazy" /></button> : <em>—</em>}
                    </td>
                    <td className="payout-col--actions">
                      <button type="button" className="cand-btn cand-btn--ghost cand-btn--xs" onClick={() => startEdit(row)} title="Edit">✎</button>
                      <button type="button" className="cand-btn cand-btn--ghost cand-btn--xs cand-btn--danger-ghost" onClick={() => handleDelete(row)} title="Delete">🗑</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* ─── FOOTER: Pagination + Close ─── */}
        <footer className="payout-modal__footer">
          {totalPages > 1 && (
            <div className="payout-modal__pagination">
              <button type="button" className="cand-btn cand-btn--ghost cand-btn--xs" disabled={page === 0} onClick={() => setPage(p => p - 1)}>← Previous</button>
              <span className="payout-modal__page-info">Page {page + 1} of {totalPages}</span>
              <button type="button" className="cand-btn cand-btn--ghost cand-btn--xs" disabled={page >= totalPages - 1} onClick={() => setPage(p => p + 1)}>Next →</button>
            </div>
          )}
          <button type="button" className="cand-btn cand-btn--ghost" onClick={onClose}>Close</button>
        </footer>
      </div>
    </div>

    {/* Lightbox for proof preview */}
    {previewProof && <div className="cand-proof-lightbox" onClick={() => setPreviewProof(null)}>
      <div className="cand-proof-lightbox-inner" onClick={ev => ev.stopPropagation()}>
        <button type="button" className="cand-proof-lightbox-close" onClick={() => setPreviewProof(null)} aria-label="Close preview">×</button>
        <img src={`${ve}${previewProof.url}`} alt={previewProof.note || previewProof.original_name || "Payment proof"} className="cand-proof-lightbox-img" />
        {previewProof.note && <p className="cand-proof-lightbox-note">{previewProof.note}</p>}
        <p className="cand-proof-lightbox-meta">{previewProof.original_name}{previewProof.uploaded_at && <span> · {new Date(previewProof.uploaded_at).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" })}</span>}</p>
      </div>
    </div>}
  </Fragment>;
}
