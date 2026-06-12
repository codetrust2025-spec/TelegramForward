/**
 * Candidates tracker UI — extracted from production teleautomation-app.jsx.
 * CSS: index.css (.cand-*). API: /candidates, /handler-expenses.
 */
import React from 'react'
import { useConfirm } from '../context/ConfirmContext.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { formatIstDate as fmtIstD, formatIstDateTime as fmtIstDt } from '../utils/istTime.js'
import { CandidatesActiveRoster } from './CandidatesActiveRoster.jsx'
import { triggerRosterDownload } from './candidatesRosterUtils.js'

const w = React
const s = { Fragment: React.Fragment }

const K1 = typeof window !== 'undefined' && window.location.port === '3000'
const ve = K1 ? '' : (typeof window !== 'undefined'
  ? `${window.location.protocol}//${window.location.host}`
  : '')

function nc() {
  return useConfirm()
}

function wu() {
  return useAuth()
}

function cR() {
  const [gate, setGate] = w.useState(null)
  const closeGate = w.useCallback(() => setGate(null), [])
  const runProtected = w.useCallback((action, opts = {}) => {
    if (typeof action === 'function') {
      setGate({
        title: opts.title || 'Admin password required',
        message: opts.message || 'Enter the main dashboard admin password to continue.',
        onVerified: () => {
          setGate(null)
          action()
        },
      })
    }
  }, [])
  return { gate, closeGate, runProtected }
}

function kx(e) {
  const t = Number(e) || 0;
  if (t < 1024) {
    return `${t} B`;
  } else if (t < 1048576) {
    return `${(t / 1024).toFixed(0)} KB`;
  } else {
    return `${(t / 1048576).toFixed(1)} MB`;
  }
}
function Nx(e) {
  if (!e) return "";
  return fmtIstDt(e) === "—" ? "" : fmtIstDt(e);
}
const bx = 8388608;
function $8({
  candidateId: e,
  proofs: t = [],
  onChange: r
}) {
  const [n, a] = w.useState(false);
  const [i, l] = w.useState("");
  const [c, o] = w.useState("");
  const [u, d] = w.useState(null);
  const [f, h] = w.useState(null);
  const [x, v] = w.useState("");
  const [g, p] = w.useState(false);
  const m = w.useRef(null);
  const _ = !e;
  const y = w.useCallback(async (b, { clearNote = true } = {}) => {
    if (!e) {
      return false;
    }
    if (b.size > bx) {
      l(`File too large (max ${bx / 1048576} MB)`);
      return false;
    }
    if (!/^image\//.test(b.type || "")) {
      l("Only image files are allowed (jpg / png / webp / gif / heic)");
      return false;
    }
    try {
      const A = new FormData();
      A.append("file", b);
      if (c.trim()) {
        A.append("note", c.trim());
      }
      const L = await (await fetch(`${ve}/candidates/${e}/proofs`, {
        method: "POST",
        body: A
      })).json();
      if (L.status !== "ok") {
        l(L.message || "Upload failed");
        return false;
      }
      if (L.candidate && r != null) {
        r(L.candidate.proofs || []);
      }
      if (clearNote) {
        o("");
      }
      return true;
    } catch (A) {
      l(A.message || "Network error");
      return false;
    }
  }, [e, r, c]);
  const M = w.useCallback(async b => {
    if (!e || !b || b.length === 0) {
      return;
    }
    const A = Array.from(b).filter(O => O && /^image\//.test(O.type || ""));
    if (!A.length) {
      l("Only image files are allowed (jpg / png / webp / gif / heic)");
      return;
    }
    l("");
    a(true);
    try {
      for (let O = 0; O < A.length; O++) {
        await y(A[O], {
          clearNote: O === A.length - 1
        });
      }
    } finally {
      a(false);
      if (m.current) {
        m.current.value = "";
      }
    }
  }, [e, y]);
  function k(b) {
    var O;
    const A = (O = b.target.files) == null ? undefined : O;
    if (A != null && A.length) {
      M(A);
    }
  }
  function T(b) {
    var O;
    b.preventDefault();
    p(false);
    const A = (O = b.dataTransfer) == null ? undefined : O.files;
    if (A != null && A.length) {
      M(A);
    }
  }
  async function S(b) {
    var A;
    if (e && window.confirm(`Remove this proof?
${b.note || b.original_name || b.filename}`)) {
      try {
        const L = await (await fetch(`${ve}/candidates/${e}/proofs/${b.id}`, {
          method: "DELETE"
        })).json();
        if (L.status === "ok") {
          if (r != null) {
            r(((A = L.candidate) == null ? undefined : A.proofs) || []);
          }
        } else {
          l(L.message || "Delete failed");
        }
      } catch (O) {
        l(O.message || "Network error");
      }
    }
  }
  async function E(b) {
    if (e) {
      try {
        const O = await (await fetch(`${ve}/candidates/${e}/proofs/${b.id}`, {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            note: x
          })
        })).json();
        if (O.status === "ok") {
          const L = t.map(M => M.id === b.id ? {
            ...M,
            note: x
          } : M);
          if (r != null) {
            r(L);
          }
          h(null);
        } else {
          l(O.message || "Save failed");
        }
      } catch (A) {
        l(A.message || "Network error");
      }
    }
  }
  w.useEffect(() => {
    function b(A) {
      if (A.key === "Escape") {
        d(null);
      }
    }
    if (u) {
      document.addEventListener("keydown", b);
    }
    return () => document.removeEventListener("keydown", b);
  }, [u]);
  return <div className="cand-proofs"><div className="cand-proofs-header"><span className="cand-field-label">Payment proofs<span className="cand-proofs-count">{t.length}</span></span>{!_ && t.length > 0 && <span className="cand-proofs-hint">Click a thumbnail to enlarge · drag to reorder is coming soon</span>}</div>{_ ? <div className="cand-proofs-empty cand-proofs-empty--blocked"><strong>Save the candidate first</strong>, then re-open this form to attach payment screenshots.</div> : <s.Fragment><div className={`cand-proofs-drop${g ? " cand-proofs-drop--active" : ""}${n ? " cand-proofs-drop--busy" : ""}`} onDragOver={b => {
        b.preventDefault();
        p(true);
      }} onDragLeave={() => p(false)} onDrop={T} onClick={() => {
        var b;
        return !n && ((b = m.current) == null ? undefined : b.click());
      }} role="button" tabIndex={0} onKeyDown={b => {
        var A;
        if (b.key === "Enter" || b.key === " ") {
          if ((A = m.current) != null) {
            A.click();
          }
        }
      }}><input ref={m} type="file" accept="image/*" multiple={true} onChange={k} hidden={true} disabled={n} /><div className="cand-proofs-drop-icon" aria-hidden={true}>📷</div><div className="cand-proofs-drop-text">{n ? <strong>Uploading…</strong> : <s.Fragment><strong>Click or drop screenshots</strong><span className="cand-proofs-drop-sub">PNG · JPG · WebP · up to 8 MB each · select multiple</span></s.Fragment>}</div></div><input className="cand-input cand-input--small" placeholder="Optional note for the next upload — e.g. ₹10k UPI · 26 May" value={c} onChange={b => o(b.target.value)} disabled={n} /></s.Fragment>}{i && <div className="cand-proofs-error">{i}</div>}{t.length > 0 && <ul className="cand-proofs-grid">{t.map(b => <li className="cand-proof-card" key={b.id}><button type="button" className="cand-proof-thumb" onClick={() => d(b)} aria-label="Preview proof"><img src={`${ve}${b.url}`} alt={b.note || b.original_name || "payment proof"} loading="lazy" /></button><div className="cand-proof-meta">{f === b.id ? <div className="cand-proof-note-edit"><input className="cand-input cand-input--small" value={x} onChange={A => v(A.target.value)} placeholder="e.g. ₹10k UPI" autoFocus={true} /><button type="button" className="cand-btn cand-btn--xs cand-btn--primary" onClick={() => E(b)}>Save</button><button type="button" className="cand-btn cand-btn--xs cand-btn--ghost" onClick={() => h(null)}>Cancel</button></div> : <button type="button" className="cand-proof-note" onClick={() => {
            h(b.id);
            v(b.note || "");
          }} title="Click to edit">{b.note || <em>add a note…</em>}</button>}<div className="cand-proof-sub"><span>{Nx(b.uploaded_at)}</span><span>·</span><span>{kx(b.size)}</span></div></div><button type="button" className="cand-proof-delete" onClick={() => S(b)} title="Delete proof" aria-label="Delete proof">×</button></li>)}</ul>}{u && <div className="cand-proof-lightbox" onClick={() => d(null)} role="dialog" aria-label="Payment proof preview"><button type="button" className="cand-proof-lightbox-close" onClick={() => d(null)} aria-label="Close preview">×</button><img src={`${ve}${u.url}`} alt={u.note || u.original_name} onClick={b => b.stopPropagation()} /><div className="cand-proof-lightbox-caption" onClick={b => b.stopPropagation()}>{u.note && <strong>{u.note}</strong>}<span>{Nx(u.uploaded_at)} · {kx(u.size)}</span><a href={`${ve}${u.url}`} download={u.original_name || u.filename} className="cand-btn cand-btn--ghost cand-btn--xs">Download</a></div></div>}</div>;
}
function _Component23({
  phone: e,
  defaultCountry: t = "91",
  inline: r = false
}) {
  const n = (e || "").trim();
  if (!n) {
    return <span className="cand-phone-empty">—</span>;
  }
  const [a, i] = w.useState(false);
  const [l, c] = w.useState("");
  const o = w.useRef(null);
  w.useEffect(() => {
    if (!a) {
      return;
    }
    function p(_) {
      if (o.current && !o.current.contains(_.target)) {
        i(false);
      }
    }
    function m(_) {
      if (_.key === "Escape") {
        i(false);
      }
    }
    document.addEventListener("mousedown", p);
    document.addEventListener("keydown", m);
    return () => {
      document.removeEventListener("mousedown", p);
      document.removeEventListener("keydown", m);
    };
  }, [a]);
  w.useEffect(() => {
    if (!l) {
      return;
    }
    const p = setTimeout(() => c(""), 1600);
    return () => clearTimeout(p);
  }, [l]);
  const u = n.replace(/[^\d+]/g, "");
  const d = u.startsWith("+") ? u : u.length === 10 ? `+${t}${u}` : `+${u}`;
  const f = d.replace(/^\+/, "");
  const h = d;
  const x = `https://wa.me/${f}`;
  async function v(p) {
    if (p != null) {
      p.stopPropagation();
    }
    try {
      await navigator.clipboard.writeText(n);
      c("Copied");
    } catch {
      try {
        const m = document.createElement("textarea");
        m.value = n;
        m.style.position = "fixed";
        m.style.opacity = "0";
        document.body.appendChild(m);
        m.select();
        document.execCommand("copy");
        document.body.removeChild(m);
        c("Copied");
      } catch {
        c("Copy failed");
      }
    }
    i(false);
  }
  function g(p) {
    p.stopPropagation();
  }
  return <span className={`cand-phone-cell${r ? " cand-phone-cell--inline" : ""}`} ref={o} onClick={g}><button type="button" className="cand-phone-trigger" onClick={p => {
      p.stopPropagation();
      i(m => !m);
    }} title="Click for call / WhatsApp / copy"><span className="cand-phone-icon" aria-hidden={true}>☎</span><span className="cand-phone-num">{n}</span></button>{a && <div className="cand-phone-menu" role="menu"><a href={h} className="cand-phone-menu-item cand-phone-menu-item--call" onClick={() => i(false)} role="menuitem"><span className="cand-phone-menu-ico" aria-hidden={true}>📞</span><span className="cand-phone-menu-text"><strong>Call</strong><em>{d}</em></span></a><a href={x} target="_blank" rel="noopener noreferrer" className="cand-phone-menu-item cand-phone-menu-item--wa" onClick={() => i(false)} role="menuitem"><span className="cand-phone-menu-ico" aria-hidden={true}>💬</span><span className="cand-phone-menu-text"><strong>WhatsApp</strong><em>wa.me/{f}</em></span></a><button type="button" className="cand-phone-menu-item cand-phone-menu-item--copy" onClick={v} role="menuitem"><span className="cand-phone-menu-ico" aria-hidden={true}>📋</span><span className="cand-phone-menu-text"><strong>Copy number</strong><em>{n}</em></span></button></div>}{l && <span className="cand-phone-toast" role="status">{l}</span>}</span>;
}
const Cu = 20000;
const k_ = 15000;
const wi = 5000;
const ki = 9000;
const B8 = 10000;
const U8 = new Set([Cu, k_, wi, ki, 0]);
function N_(e) {
  if (e) {
    return k_;
  } else {
    return Cu;
  }
}
function os(e, t, r) {
  if (e === "round_wise") {
    if (r === "non_domestic") {
      return ki;
    } else {
      return wi;
    }
  } else {
    return N_(t);
  }
}
function z8(e) {
  if ((e == null ? undefined : e.service_type) === "round_wise" || (e == null ? undefined : e.service_type) === "profile_service") {
    return {
      service_type: e.service_type,
      interview_scope: e.interview_scope === "non_domestic" ? "non_domestic" : "domestic"
    };
  }
  const t = Number(e == null ? undefined : e.expected_payment) || 0;
  if (t === wi) {
    return {
      service_type: "round_wise",
      interview_scope: "domestic"
    };
  } else if (t === ki) {
    return {
      service_type: "round_wise",
      interview_scope: "non_domestic"
    };
  } else {
    return {
      service_type: "profile_service",
      interview_scope: "domestic"
    };
  }
}
function $n(e) {
  const t = Number(e) || 0;
  if (t) {
    return `₹${t.toLocaleString("en-IN")}`;
  } else {
    return "₹0";
  }
}
function b_(e) {
  if (e.service_type === "round_wise") {
    if (e.interview_scope === "non_domestic") {
      return ki;
    } else {
      return wi;
    }
  }
  const t = Number(e.expected_payment) || os(e.service_type, e.consultancy, e.interview_scope);
  return Math.min(B8, t);
}
function W8(e) {
  if (!e.slots_group_posted) {
    return "Confirm the slot screenshot was posted in the Interview slots WhatsApp group first.";
  }
  const t = (e.reference || "").trim();
  if (!t || t.toLowerCase() === "unknown") {
    return "Assign an owner (reference) before confirming the interview slot.";
  }
  const r = Number(e.payment) || 0;
  const n = b_(e);
  if (r < n) {
    return `Record at least ${$n(n)} received (currently ${$n(r)}).`;
  } else if ((e.date || "").trim()) {
    return null;
  } else {
    return "Set the interview date before confirming the slot.";
  }
}
const V8 = [{
  value: "in_progress",
  label: "In progress"
}, {
  value: "completed",
  label: "Completed"
}, {
  value: "fail",
  label: "Failed"
}, {
  value: "dropped",
  label: "Dropped"
}];
const H8 = ["SAP BASIS", "SAP Sales", "SAP MM", "SAP HANA", "Salesforce", "ServiceNow", "React JS", "Java Backend", "Node JS", "Python", "AWS Admin", "AWS Cloud", "AWS DevOps", "Azure DevOps", "Azure Admin", "Cloud", "Cloud DevOps", "DevOps", "Testing", "ETL", "Oracle Fusion (Tech Con)", "Oracle Fusion (Func)", "Data Engineer", "Data Analyst", "ML Engineer"];
function G8() {
  return {
    name: "",
    stage: "in_progress",
    technology: "",
    task: "not_started",
    phone: "",
    reference: "",
    service_type: "profile_service",
    interview_scope: "domestic",
    consultancy: false,
    payment: "",
    expected_payment: String(Cu),
    follow_up: "",
    date: new Date().toISOString().slice(0, 10),
    time: "",
    expenses: "",
    notes: "",
    slot_confirmed: false,
    slots_group_posted: false
  };
}
function K8(e) {
  const t = !!e.consultancy;
  const {
    service_type: r,
    interview_scope: n
  } = z8(e);
  return {
    name: e.name || "",
    stage: e.stage || "in_progress",
    technology: e.technology || "",
    task: e.task || "not_started",
    phone: e.phone || "",
    reference: e.reference || "",
    service_type: r,
    interview_scope: n,
    consultancy: r === "round_wise" ? false : t,
    payment: e.payment ? String(e.payment) : "",
    expected_payment: e.expected_payment ? String(e.expected_payment) : String(os(r, t, n)),
    follow_up: e.follow_up || "",
    date: e.date || "",
    time: e.time || "",
    expenses: e.expenses || "",
    notes: e.notes || "",
    slot_confirmed: !!e.slot_confirmed,
    slots_group_posted: !!e.slots_group_posted
  };
}
function X8({
  initial: e,
  onClose: t,
  onSave: r,
  handlerReference: n = null,
  lockReference: a = false,
  isAdmin: i = false
}) {
  const [l, c] = w.useState(() => {
    if (e) {
      return K8(e);
    }
    const C = G8();
    if (n) {
      C.reference = n;
    }
    return C;
  });
  const [o, u] = w.useState(() => Array.isArray(e == null ? undefined : e.proofs) ? e.proofs : []);
  const [d, f] = w.useState(false);
  const [h, x] = w.useState("");
  const v = w.useRef(null);
  w.useEffect(() => {
    u(Array.isArray(e == null ? undefined : e.proofs) ? e.proofs : []);
  }, [e == null ? undefined : e.id]);
  w.useEffect(() => {
    var C;
    if ((C = v.current) != null) {
      C.focus();
    }
  }, []);
  w.useEffect(() => {
    function C(Y) {
      if (Y.key === "Escape") {
        if (t != null) {
          t();
        }
      }
    }
    document.addEventListener("keydown", C);
    return () => document.removeEventListener("keydown", C);
  }, [t]);
  function g(C, Y) {
    c(J => ({
      ...J,
      [C]: Y
    }));
  }
  function p(C) {
    const Y = Number(C.expected_payment) || 0;
    if (U8.has(Y)) {
      return String(os(C.service_type, C.consultancy, C.interview_scope));
    } else {
      return C.expected_payment;
    }
  }
  function m(C) {
    c(Y => {
      const J = {
        ...Y,
        service_type: C,
        consultancy: C === "round_wise" ? false : Y.consultancy,
        slot_confirmed: C === "round_wise" ? Y.slot_confirmed : false,
        slots_group_posted: C === "round_wise" ? Y.slots_group_posted : false
      };
      return {
        ...J,
        expected_payment: p(J)
      };
    });
  }
  function _(C) {
    c(Y => {
      const J = {
        ...Y,
        interview_scope: C
      };
      return {
        ...J,
        expected_payment: p(J)
      };
    });
  }
  function y(C) {
    c(Y => {
      const J = {
        ...Y,
        consultancy: C
      };
      return {
        ...J,
        expected_payment: p(J)
      };
    });
  }
  const k = Number(l.payment) || 0;
  const T = Number(l.expected_payment) || os(l.service_type, l.consultancy, l.interview_scope);
  const S = Math.max(0, T - k);
  const E = w.useMemo(() => k <= 0 ? "unpaid" : k >= T ? "paid" : "partial", [k, T]);
  const b = S > 0;
  const A = W8(l);
  const O = !A;
  const L = b_(l);
  const [refOptions, setRefOptions] = w.useState([]);
  w.useEffect(() => {
    fetch(`${ve}/candidates/references`, {
      credentials: "include"
    }).then(C => C.json()).then(C => {
      if (C.status === "ok") {
        setRefOptions(C.references || []);
      }
    }).catch(() => {});
  }, []);
  const refList = w.useMemo(() => {
    const names = new Set();
    for (const R of refOptions) {
      const s = (R || "").trim();
      if (s) {
        names.add(s);
      }
    }
    if (n) {
      names.add(n.trim());
    }
    const cur = (l.reference || "").trim();
    if (cur) {
      names.add(cur);
    }
    return Array.from(names).sort((Be, Xe) => Be.localeCompare(Xe));
  }, [refOptions, n, l.reference]);
  async function M(C) {
    var Y;
    if ((Y = C == null ? undefined : C.preventDefault) != null) {
      Y.call(C);
    }
    if (!l.name.trim()) {
      x("Name is required");
      return;
    }
    if (b && !l.follow_up.trim()) {
      x(`₹${S.toLocaleString("en-IN")} balance pending — add a short follow-up / remark before saving.`);
      return;
    }
    if (l.slot_confirmed && A && !i) {
      x(A);
      return;
    }
    f(true);
    x("");
    try {
      const J = {
        ...l,
        service_type: l.service_type,
        interview_scope: l.service_type === "round_wise" ? l.interview_scope : "",
        consultancy: l.service_type === "round_wise" ? false : !!l.consultancy,
        payment: l.payment === "" ? 0 : Number(l.payment),
        expected_payment: l.expected_payment === "" ? os(l.service_type, l.consultancy, l.interview_scope) : Number(l.expected_payment),
        follow_up: b ? l.follow_up.trim() : "",
        slot_confirmed: l.service_type === "round_wise" ? !!l.slot_confirmed : false,
        slots_group_posted: l.service_type === "round_wise" ? !!l.slots_group_posted : false
      };
      await r(J);
    } catch (J) {
      x(J.message || "Save failed");
    } finally {
      f(false);
    }
  }
  return <div className="cand-modal-backdrop" onClick={C => C.target === C.currentTarget && (t == null ? undefined : t())}><form className="cand-modal" onSubmit={M}><header className="cand-modal-header"><h3 className="cand-modal-title">{e ? "Edit candidate" : "Add candidate"}</h3><button type="button" className="cand-modal-close" onClick={t} aria-label="Close">×</button></header><div className="cand-modal-body"><label className="cand-field cand-field--span2"><span className="cand-field-label">Candidate name *</span><input ref={v} className="cand-input" value={l.name} onChange={C => g("name", C.target.value)} placeholder="e.g. NIKHIL" required={true} /></label><label className="cand-field"><span className="cand-field-label">Stage</span><select className="cand-input" value={l.stage} onChange={C => g("stage", C.target.value)}>{V8.map(C => <option value={C.value} key={C.value}>{C.label}</option>)}</select></label><label className="cand-field cand-field--span2"><span className="cand-field-label">Technology</span><input className="cand-input" value={l.technology} onChange={C => g("technology", C.target.value)} placeholder="e.g. SAP BASIS, React JS, AWS Admin…" list="cand-tech-list" /><datalist id="cand-tech-list">{H8.map(C => <option value={C} key={C} />)}</datalist></label><label className="cand-field"><span className="cand-field-label">Phone{l.phone && <span className="cand-field-aside"><_Component23 phone={l.phone} inline={true} /></span>}</span><input className="cand-input" type="tel" value={l.phone} onChange={C => g("phone", C.target.value.replace(/[^\d+]/g, ""))} placeholder="9876543210" /></label><label className="cand-field"><span className="cand-field-label">Reference</span><select className="cand-input" value={l.reference} onChange={C => g("reference", C.target.value)} disabled={a} title={a ? "Your handler name is set automatically" : undefined} required={!a}>{!l.reference && !a && <option value="">Select referrer…</option>}{refList.map(R => <option value={R} key={R}>{R}</option>)}</select><span className="cand-field-hint">Whoever referred this lead. Earns 50% of every rupee the client pays — regardless of channel.</span></label><div className="cand-field cand-field--span2 cand-service-field"><span className="cand-field-label">Interview support service</span><div className="cand-service-options"><label className={`cand-service-card${l.service_type === "profile_service" ? " cand-service-card--on" : ""}`}><input type="radio" name="cand-service-type" checked={l.service_type === "profile_service"} onChange={() => m("profile_service")} /><span className="cand-service-card-body"><strong>Profile service</strong><em>Full profile placement · baseline ₹{Cu.toLocaleString("en-IN")}</em></span></label><label className={`cand-service-card${l.service_type === "round_wise" ? " cand-service-card--on" : ""}`}><input type="radio" name="cand-service-type" checked={l.service_type === "round_wise"} onChange={() => m("round_wise")} /><span className="cand-service-card-body"><strong>Round-wise support</strong><em>Per interview round · ₹{wi.toLocaleString("en-IN")} domestic · ₹{ki.toLocaleString("en-IN")} non-domestic</em></span></label></div></div>{l.service_type === "round_wise" && <div className="cand-field cand-field--span2 cand-service-scope"><span className="cand-field-label">Round-wise scope</span><div className="cand-service-scope-options"><label className={`cand-service-scope-pill${l.interview_scope === "domestic" ? " cand-service-scope-pill--on" : ""}`}><input type="radio" name="cand-interview-scope" checked={l.interview_scope === "domestic"} onChange={() => _("domestic")} />Domestic · ₹{wi.toLocaleString("en-IN")}</label><label className={`cand-service-scope-pill${l.interview_scope === "non_domestic" ? " cand-service-scope-pill--on" : ""}`}><input type="radio" name="cand-interview-scope" checked={l.interview_scope === "non_domestic"} onChange={() => _("non_domestic")} />Non-domestic · ₹{ki.toLocaleString("en-IN")}</label></div></div>}{l.service_type === "profile_service" && <label className={`cand-field cand-consultancy-field${l.consultancy ? " cand-consultancy-field--on" : ""}`}><span className="cand-field-label">Acquisition channel</span><div className="cand-consultancy-toggle"><input type="checkbox" id="cand-consultancy-cb" checked={!!l.consultancy} onChange={C => y(C.target.checked)} /><label htmlFor="cand-consultancy-cb" className="cand-consultancy-label"><span className="cand-consultancy-pip" aria-hidden={true} /><span className="cand-consultancy-text"><strong>{l.consultancy ? "From a consultancy" : "Direct lead"}</strong><em>Baseline ₹{N_(l.consultancy).toLocaleString("en-IN")}{l.consultancy ? " — consultancy takes their cut, we charge less" : " — full ₹20,000 profile service"}</em></span></label></div></label>}<label className="cand-field cand-field--span2"><span className="cand-field-label">Expected ₹ (initial amount)</span><input className="cand-input" type="number" min="0" step="500" value={l.expected_payment} onChange={C => g("expected_payment", C.target.value)} placeholder={String(os(l.service_type, l.consultancy, l.interview_scope))} /><span className="cand-field-hint">Auto-set to ₹{os(l.service_type, l.consultancy, l.interview_scope).toLocaleString("en-IN")} for {l.service_type === "round_wise" ? `${l.interview_scope === "non_domestic" ? "non-domestic" : "domestic"} round-wise support` : l.consultancy ? "consultancy profile service" : "direct profile service"} — change only if you've agreed on a different price.</span></label><label className="cand-field"><span className="cand-field-label">Received ₹</span><input className="cand-input" type="number" min="0" step="500" value={l.payment} onChange={C => g("payment", C.target.value)} placeholder="0" /><span className={`cand-pay-status cand-pay-status--${E}`}>{E === "paid" && <s.Fragment>✓ Paid in full ({$n(k)})</s.Fragment>}{E === "partial" && <s.Fragment>● {$n(k)} of {$n(T)} · <strong>{$n(S)} pending</strong></s.Fragment>}{E === "unpaid" && <s.Fragment>○ Nothing received yet · <strong>{$n(T)} pending</strong></s.Fragment>}</span>{k > 0 && (l.reference || "").trim() && <span className="cand-pay-handler-share" title="The referrer automatically earns 50% of every rupee the client pays the business.">↻ Handler <strong>{l.reference.trim()}</strong> earns <strong className="cand-pay-handler-amt">{$n(Math.floor(k * 0.5))}</strong> (50% of {$n(k)} received)</span>}</label>{b && <label className="cand-field cand-field--span2 cand-field--required"><span className="cand-field-label">Follow-up / remark<span className="cand-field-required-tag">required · balance {$n(S)}</span></span><textarea className="cand-input cand-input--textarea" rows={2} value={l.follow_up} onChange={C => g("follow_up", C.target.value)} placeholder="e.g. Will pay ₹10k by 5th June after offer letter · Awaiting husband approval · Partial payment until interview clears" required={true} /><span className="cand-field-hint">Why is the balance still pending? When the operator will be paid? This appears as a chip on the candidate row.</span></label>}<div className="cand-field cand-field--span2"><$8 candidateId={e == null ? undefined : e.id} proofs={o} onChange={u} /></div><label className="cand-field"><span className="cand-field-label">Date</span><input className="cand-input" type="date" value={l.date} onChange={C => g("date", C.target.value)} /></label><label className="cand-field"><span className="cand-field-label">Time</span><input className="cand-input" type="time" value={l.time} onChange={C => g("time", C.target.value)} /></label>{l.service_type === "round_wise" && <s.Fragment><div className="cand-field cand-field--span2 cand-slots-group"><span className="cand-field-label">Interview slots group</span><label className="cand-slot-confirm-toggle"><input type="checkbox" checked={!!l.slots_group_posted} onChange={C => g("slots_group_posted", C.target.checked)} /><span className="cand-slot-confirm-text"><strong>Posted in slots WhatsApp group</strong><em>Required before marking slot confirmed (screenshot + time)</em></span></label></div><div className={`cand-field cand-field--span2 cand-slot-confirm${l.slot_confirmed ? " cand-slot-confirm--on" : ""}`}><span className="cand-field-label">Interview slot</span><label className="cand-slot-confirm-toggle"><input type="checkbox" checked={!!l.slot_confirmed} disabled={!O && !i} onChange={C => g("slot_confirmed", C.target.checked)} /><span className="cand-slot-confirm-text"><strong>{l.slot_confirmed ? "Slot confirmed" : "Mark slot confirmed"}</strong><em>Requires owner, ≥{$n(L)} received, and interview date{i && A ? " · admin may override" : ""}</em></span></label>{A && !l.slot_confirmed && <span className="cand-field-hint cand-slot-confirm-block">{A}</span>}{l.slot_confirmed && (e == null ? undefined : e.slot_confirmed_at) && <span className="cand-field-hint">Confirmed {fmtIstDt(e.slot_confirmed_at)}</span>}</div></s.Fragment>}<label className="cand-field"><span className="cand-field-label">Expenses (free text)</span><input className="cand-input" value={l.expenses} onChange={C => g("expenses", C.target.value)} placeholder="e.g. 3000 fuel, 12000 gym" /></label><label className="cand-field cand-field--span2"><span className="cand-field-label">Notes</span><textarea className="cand-input cand-input--textarea" rows={3} value={l.notes} onChange={C => g("notes", C.target.value)} placeholder="Any extra context — e.g. follow-up engagement, second round, duplicate entry…" /></label></div>{h && <div className="cand-modal-error">{h}</div>}<footer className="cand-modal-footer"><button type="button" className="cand-btn cand-btn--ghost" onClick={t} disabled={d}>Cancel</button><button type="submit" className="cand-btn cand-btn--primary" disabled={d}>{d ? "Saving…" : e ? "Save changes" : "Add candidate"}</button></footer></form></div>;
}
function cr(e) {
  const t = Number(e) || 0;
  if (t === 0) {
    return "₹0";
  } else if (t < 100000) {
    return `₹${t.toLocaleString("en-IN")}`;
  } else {
    return `₹${(t / 100000).toFixed(t % 100000 === 0 ? 0 : 1)}L`;
  }
}
function J8({
  stats: e,
  scopeLabel: t,
  onPayoutsClick: r,
  handlerView: n = false,
  handlerName: a = null,
  scopeReference: scopeRef = null
}) {
  var d;
  var f;
  var h;
  if (!e) {
    return null;
  }
  const scopeKey = (scopeRef || (n && a ? a : null) || "").trim().toLowerCase();
  const scopedPerf = scopeKey ? (e.top_performers || []).find(y => (y.name || "").trim().toLowerCase() === scopeKey) : null;
  const i = scopedPerf ? scopedPerf.count || 0 : Object.values(e.by_stage || {}).reduce((x, v) => x + v, 0);
  const l = scopedPerf ? scopedPerf.completed || 0 : ((d = e.by_stage) == null ? undefined : d.completed) || 0;
  const c = scopedPerf ? scopedPerf.in_progress || 0 : ((f = e.by_stage) == null ? undefined : f.in_progress) || 0;
  const o = scopedPerf ? scopedPerf.fail || 0 : ((h = e.by_stage) == null ? undefined : h.fail) || 0;
  const u = i > 0 ? Math.round(l / i * 100) : 0;
  const revenueTotal = scopedPerf ? scopedPerf.revenue_total || 0 : e.revenue_total;
  const revenueCompleted = scopedPerf ? scopedPerf.revenue_completed || 0 : e.revenue_completed;
  const pendingTotal = scopedPerf ? scopedPerf.pending_total || 0 : e.pending_total;
  const pendingCount = scopedPerf ? scopedPerf.pending_count || 0 : e.pending_count;
  const showChannelPills = !scopeKey && (e.consultancy_count || 0) > 0;
  return <div className="cand-stats"><div className="cand-stat-card"><div className="cand-stat-label">Total candidates{t && <span className="cand-stat-scope">{t}</span>}</div><div className="cand-stat-value">{i}</div><div className="cand-stat-sub">{l} done · {c} active · {o} failed</div>{showChannelPills && <div className="cand-stat-channel"><span className="cand-channel-pill cand-channel-pill--direct" title={`Direct leads · ₹${(e.default_expected_payment || 20000).toLocaleString("en-IN")} baseline`}>Direct <strong>{e.direct_count || 0}</strong></span><span className="cand-channel-pill cand-channel-pill--consultancy" title={`Consultancy leads · ₹${(e.consultancy_expected_payment || 15000).toLocaleString("en-IN")} baseline`}>Consultancy <strong>{e.consultancy_count || 0}</strong></span></div>}</div><div className="cand-stat-card"><div className="cand-stat-label">Total revenue{t && <span className="cand-stat-scope">{t}</span>}</div><div className="cand-stat-value cand-stat-value--money">{cr(revenueTotal)}</div><div className="cand-stat-sub">From completed: {cr(revenueCompleted)}</div></div><div className="cand-stat-card"><div className="cand-stat-label">Conversion{t && <span className="cand-stat-scope">{t}</span>}</div><div className="cand-stat-value">{u}%</div><div className="cand-stat-sub">{l} of {i} reached completed</div></div><div className={`cand-stat-card${(pendingCount || 0) > 0 ? " cand-stat-card--alert" : ""}`}><div className="cand-stat-label">Pending collections{t && <span className="cand-stat-scope">{t}</span>}</div><div className="cand-stat-value cand-stat-value--money cand-stat-value--alert">{cr(pendingTotal)}</div><div className="cand-stat-sub">{(pendingCount || 0) === 0 ? <s.Fragment>All candidates paid the ₹{(e.default_expected_payment || 20000).toLocaleString("en-IN")} baseline.</s.Fragment> : <s.Fragment><strong>{pendingCount}</strong> short of baseline{(e.pending_no_remark || 0) > 0 && <s.Fragment> · <strong className="cand-stat-warn">{e.pending_no_remark}</strong> missing remark</s.Fragment>}</s.Fragment>}</div></div>{(() => {
      const x = scopedPerf ? Number(scopedPerf.auto_earnings_total) || 0 : e.handler_auto_earnings_total ?? e.handler_earnings_total ?? 0;
      const v = scopedPerf ? Number(scopedPerf.paid_out_total) || 0 : e.handler_paid_out_total ?? e.handler_deductions_total ?? 0;
      const g = scopedPerf ? Number(scopedPerf.net_payable) || 0 : x - v;
      const salaryTotal = scopedPerf ? Number(scopedPerf.salary_total) || 0 : e.handler_salary_total || 0;
      const commissionTotal = scopedPerf ? Number(scopedPerf.commission_total) || 0 : e.handler_commission_total ?? x - salaryTotal;
      const p = e.commission_pct || 50;
      const m = (e.top_performers || []).map(y => ({
        name: y.name,
        owe: Math.max(0, Number(y.net_payable) || 0),
        base: Number(y.auto_earnings_total) || 0,
        paid: Number(y.paid_out_total) || 0,
        salary: Number(y.salary_total) || 0,
        commission: Number(y.commission_total ?? y.auto_earnings_total) || 0
      })).filter(y => y.owe > 0).filter(y => !scopeKey || y.name.trim().toLowerCase() === scopeKey).sort((y, k) => k.owe - y.owe);
      const _ = (e.top_performers || []).map(y => ({
        name: y.name,
        over: Math.max(0, -(Number(y.net_payable) || 0))
      })).filter(y => y.over > 0).sort((y, k) => k.over - y.over);
      return <button type="button" className={`cand-stat-card cand-stat-card--clickable cand-stat-card--payouts${g > 0 ? " cand-stat-card--owe" : g < 0 ? " cand-stat-card--alert" : ""}`} onClick={() => r == null ? undefined : r()} title={n ? "View your earnings breakdown" : "Click to view payout board — admin password required"}><div className="cand-stat-label">{n ? "My earnings" : "Handler payouts"}{t && <span className="cand-stat-scope">{t}</span>}<span className="cand-stat-arrow" aria-hidden={true}>→</span></div><div className={`cand-stat-value cand-stat-value--money ${g > 0 ? "cand-stat-value--earn" : g === 0 ? "" : "cand-stat-value--alert"}`}>{n ? g > 0 ? `Pending ${cr(g)}` : g === 0 ? "Settled" : `Overpaid ${cr(Math.abs(g))}` : <s.Fragment>{g > 0 ? "Owe " : g === 0 ? "Settled" : "Overpaid "}{g !== 0 && cr(Math.abs(g))}</s.Fragment>}</div>{m.length > 0 ? <ul className="cand-payto-list" aria-label={n ? "Your earnings breakdown" : "Handlers still owed money"}>{m.slice(0, 4).map(y => <li className="cand-payto-row" key={y.name}>{!n && <span className="cand-payto-action">Pay</span>}<span className="cand-payto-name">{n ? "Your share" : y.name}{y.salary > 0 && <em className="cand-payto-mix" title={`Salary ${cr(y.salary)} + commission ${cr(y.commission)} − paid ${cr(y.paid)}`}>salary {cr(y.salary)} + comm. {cr(y.commission)}</em>}</span><span className="cand-payto-amount">{cr(y.owe)}</span></li>)}{m.length > 4 && <li className="cand-payto-more">+ {m.length - 4} more · click for full list</li>}</ul> : g === 0 ? <div className="cand-payto-empty cand-payto-empty--settled">✓ Everyone is paid up.</div> : null}{_.length > 0 && <ul className="cand-payto-list cand-payto-list--over" aria-label="Handlers who have been over-paid">{_.slice(0, 3).map(y => <li className="cand-payto-row cand-payto-row--over" key={y.name}><span className="cand-payto-action">Recover from</span><span className="cand-payto-name">{y.name}</span><span className="cand-payto-amount">{cr(y.over)}</span></li>)}</ul>}<div className="cand-stat-sub"><strong className="cand-net-pos">{cr(x)}</strong> owed{salaryTotal > 0 ? <span title="Owed = salaries + 50% commission on receipts"> ({cr(salaryTotal)} salary + {cr(commissionTotal)} comm.)</span> : <s.Fragment> ({p}%)</s.Fragment>} · <strong className="cand-net-neg">{cr(v)}</strong> paid out</div></button>;
    })()}<div className="cand-stat-card cand-stat-card--list"><div className="cand-stat-label">Top technologies (by revenue){t && <span className="cand-stat-scope">{t}</span>}</div><ul className="cand-stat-list">{(e.top_technologies || []).slice(0, 5).map(x => <li key={x.name}><span className="cand-stat-list-name">{x.name}</span><span className="cand-stat-list-value">{cr(x.revenue)}</span></li>)}{(e.top_technologies || []).length === 0 && <li className="cand-stat-list-empty">No data yet.</li>}</ul></div></div>;
}
function $a(e) {
  const t = Number(e) || 0;
  if (t === 0) {
    return "₹0";
  } else if (t < 100000) {
    return `₹${t.toLocaleString("en-IN")}`;
  } else {
    return `₹${(t / 100000).toFixed(t % 100000 === 0 ? 0 : 1)}L`;
  }
}
const Q8 = [{
  value: "revenue_completed",
  label: "Completed ₹"
}, {
  value: "revenue_total",
  label: "Total ₹"
}, {
  value: "count",
  label: "Lead count"
}, {
  value: "conversion_pct",
  label: "Conversion %"
}];
function Z8(e, t) {
  if (t === "count") {
    return {
      primary: `${e.count}`,
      primaryLabel: e.count === 1 ? "lead" : "leads",
      secondary: e.revenue_total ? `₹${e.revenue_total.toLocaleString("en-IN")} pipeline` : null
    };
  } else if (t === "conversion_pct") {
    return {
      primary: `${e.conversion_pct}%`,
      primaryLabel: "conversion",
      secondary: `${e.completed} of ${e.count} closed`
    };
  } else if (t === "revenue_total") {
    return {
      primary: $a(e.revenue_total),
      primaryLabel: "pipeline",
      secondary: e.revenue_completed > 0 ? `${$a(e.revenue_completed)} closed` : "none closed yet"
    };
  } else {
    return {
      primary: $a(e.revenue_completed),
      primaryLabel: "closed",
      secondary: e.revenue_total > e.revenue_completed ? `${$a(e.revenue_total - e.revenue_completed)} still in pipeline` : null
    };
  }
}
function eR(e, t) {
  const r = [...(e || [])];
  r.sort((n, a) => {
    const i = Number(n == null ? undefined : n[t]) || 0;
    const l = Number(a == null ? undefined : a[t]) || 0;
    if (l !== i) {
      return l - i;
    } else {
      return (Number(a == null ? undefined : a.revenue_total) || 0) - (Number(n == null ? undefined : n.revenue_total) || 0);
    }
  });
  return r;
}
function _Component26({
  stats: e,
  month: t,
  onMonthChange: r,
  monthOptions: n,
  onExpensesChanged: a,
  onShowEarnings: i,
  onEditPayout: l,
  handlerView: c = false,
  handlerName: o = null,
  scopeReference: scopeRef = null
}) {
  const [u, d] = w.useState("revenue_completed");
  const scopeKey = (scopeRef || (c && o ? o : null) || "").trim().toLowerCase();
  const f = w.useMemo(() => {
    const m = (e == null ? undefined : e.top_performers) || [];
    if (!c || !o) {
      return m;
    }
    const _ = o.trim().toLowerCase();
    return m.filter(y => (y.name || "").trim().toLowerCase() === _);
  }, [e == null ? undefined : e.top_performers, c, o]);
  const h = w.useMemo(() => eR(f, u), [f, u]);
  const x = w.useMemo(() => Math.max(1, ...h.map(m => Number(m == null ? undefined : m[u]) || 0)), [h, u]);
  const v = w.useMemo(() => {
    if (!t || t === "all") {
      return null;
    }
    const m = (n || []).find(_ => _.value === t);
    if (m) {
      return m.label.replace(" · this month", "");
    } else {
      return t;
    }
  }, [t, n]);
  const g = w.useMemo(() => {
    if (!e) {
      return null;
    }
    if (scopeKey) {
      const row = f.find(m => (m.name || "").trim().toLowerCase() === scopeKey) || f[0];
      if (row) {
        return {
          total: row.count || 0,
          revenue: row.revenue_total || 0,
          completed: row.revenue_completed || 0,
          label: (row.count || 0) === 1 ? "candidate" : "candidates"
        };
      }
    }
    return {
      total: e.total || 0,
      revenue: e.revenue_total || 0,
      completed: e.revenue_completed || 0,
      label: (e.total || 0) === 1 ? "candidate" : "candidates"
    };
  }, [e, scopeKey, f]);
  const p = c ? "My performance" : "Top performers";
  if (!f.length && !v) {
    return <section className="cand-top-perf"><header className="cand-top-perf-header"><h3 className="cand-top-perf-title">{p}</h3><p className="cand-top-perf-sub">{c ? "No referred candidates yet for this period." : "No candidates yet — add some to see who's bringing in business."}</p></header></section>;
  } else {
    return <section className="cand-top-perf"><header className="cand-top-perf-header"><div><h3 className="cand-top-perf-title">{p}{v && <span className="cand-top-perf-scope-tag">{v}</span>}</h3><p className="cand-top-perf-sub">{c ? <s.Fragment>{o ? <strong>{o}</strong> : "Your leads"}{v ? <s.Fragment> · <strong>{v}</strong></s.Fragment> : null} — your revenue and commission only.</s.Fragment> : v ? <s.Fragment>Scoped to <strong>{v}</strong> — ranked by completed revenue.</s.Fragment> : <s.Fragment>All time — ranked by completed revenue.</s.Fragment>}{g && <s.Fragment> · <strong>{g.total}</strong> {g.label} · <strong>{$a(g.revenue)}</strong> total{g.completed > 0 && <s.Fragment> · <strong>{$a(g.completed)}</strong> completed</s.Fragment>}</s.Fragment>}</p></div><div className="cand-top-perf-controls">{i && !c && <button type="button" className="cand-btn cand-btn--primary cand-top-perf-earn-btn" onClick={i} title="Open a full board with every handler's salary, commission, paid out and net owed — with chart view"><span aria-hidden={true} style={{
              marginRight: 6
            }}>📊</span>Total earnings</button>}{r && (n == null ? undefined : n.length) > 0 && <div className="cand-top-perf-control"><label className="cand-top-perf-sort-label">Month</label><select className="cand-input cand-input--compact" value={t || "all"} onChange={m => r(m.target.value)} aria-label="Filter by month">{n.map(m => <option value={m.value} key={m.value}>{m.label}</option>)}</select></div>}<div className="cand-top-perf-control"><label className="cand-top-perf-sort-label">Sort by</label><select className="cand-input cand-input--compact" value={u} onChange={m => d(m.target.value)}>{Q8.map(m => <option value={m.value} key={m.value}>{m.label}</option>)}</select></div></div></header>{h.length === 0 ? <p className="cand-top-perf-empty">{v ? <s.Fragment>No candidates in <strong>{v}</strong>. Try a different month or clear the filter.</s.Fragment> : <s.Fragment>No candidates yet.</s.Fragment>}</p> : <ol className="cand-perf-list">{h.map((m, _) => {
          const y = Number(m == null ? undefined : m[u]) || 0;
          const k = y === 0 ? 2 : Math.max(2, Math.round(y / x * 100));
          const T = _ + 1;
          const S = T === 1 ? "cand-perf-rank--1" : T === 2 ? "cand-perf-rank--2" : T === 3 ? "cand-perf-rank--3" : "";
          const E = Z8(m, u);
          const b = y === 0 && (u === "revenue_completed" || u === "revenue_total");
          return <li className="cand-perf-row" key={m.ref_key || m.name.toLowerCase()}><span className={`cand-perf-rank ${S}`} aria-hidden={true}>{T}</span><div className="cand-perf-body"><div className="cand-perf-line1"><span className="cand-perf-name" title={m.name}>{m.name}</span><span className="cand-perf-headline"><span className={`cand-perf-revenue${b ? " cand-perf-revenue--muted" : ""}`}>{E.primary}</span><span className="cand-perf-headline-label">{E.primaryLabel}</span>{E.secondary && <span className="cand-perf-headline-sub">· {E.secondary}</span>}</span></div><div className="cand-perf-bar-wrap" aria-hidden={true}><div className="cand-perf-bar" style={{
                  width: `${k}%`
                }} /></div><div className="cand-perf-line2"><span className="cand-perf-stat"><strong>{m.count}</strong> lead{m.count === 1 ? "" : "s"}</span><span className="cand-perf-stat cand-perf-stat--good">{m.completed} done</span>{m.in_progress > 0 && <span className="cand-perf-stat cand-perf-stat--info">{m.in_progress} active</span>}{m.fail > 0 && <span className="cand-perf-stat cand-perf-stat--bad">{m.fail} failed</span>}<span className="cand-perf-stat cand-perf-stat--muted">{m.conversion_pct}% conversion</span><span className="cand-perf-stat cand-perf-stat--money">{$a(m.revenue_total)} total</span>{(m.salary_total || 0) > 0 && <span className="cand-perf-stat cand-perf-stat--salary" title={`Fixed base salary · ₹${(m.salary_monthly || 0).toLocaleString("en-IN")}/month`}>₹{m.salary_total.toLocaleString("en-IN")} salary<em className="cand-perf-stat-em">(base)</em></span>}{(m.commission_total ?? m.auto_earnings_total ?? 0) > 0 && <span className="cand-perf-stat cand-perf-stat--earning" title={`Auto-computed: ${m.commission_pct || 50}% of every rupee the client paid to the business goes to the referrer.`}>₹{(m.commission_total ?? m.auto_earnings_total ?? 0).toLocaleString("en-IN")} commission<em className="cand-perf-stat-em">({m.commission_pct || 50}%)</em></span>}{(m.paid_out_total || 0) > 0 && <span className="cand-perf-stat cand-perf-stat--deduction" title="Money already paid out to / for this handler from the ledger">−₹{m.paid_out_total.toLocaleString("en-IN")} paid</span>}{((m.auto_earnings_total || 0) > 0 || (m.paid_out_total || 0) > 0) && <span className={`cand-perf-stat cand-perf-stat--net${(m.net_payable || 0) > 0 ? " cand-perf-stat--net-pos" : " cand-perf-stat--net-neg"}`} title="Net owed = (50% of client payments) − (already paid out). Positive means the operator still owes the handler.">{(m.net_payable || 0) > 0 ? "Owe" : (m.net_payable || 0) === 0 ? "Settled" : "Overpaid"} {$a(Math.abs(m.net_payable || 0))}</span>}{!c && l && <button type="button" className="cand-perf-exp-btn" onClick={() => l(m)} title="Log a payout to / for this handler (admin password required)">{(m.paid_out_count || m.expenses_count || 0) > 0 ? `Edit ${m.paid_out_count || m.expenses_count} payout${(m.paid_out_count || m.expenses_count) === 1 ? "" : "s"}` : "+ Log payout"}</button>}</div></div></li>;
        })}</ol>}</section>;
  }
}
const B0 = [{
  value: "commission",
  label: "Commission payout"
}, {
  value: "travel",
  label: "Travel / fuel"
}, {
  value: "food",
  label: "Food / meals"
}, {
  value: "gym",
  label: "Gym / health"
}, {
  value: "equipment",
  label: "Equipment"
}, {
  value: "marketing",
  label: "Marketing"
}, {
  value: "software",
  label: "Software / tools"
}, {
  value: "other",
  label: "Other"
}];
const Ex = Object.fromEntries(B0.map(e => [e.value, e.label]));
function Jc(e) {
  const t = Number(e) || 0;
  if (t) {
    return `₹${t.toLocaleString("en-IN")}`;
  } else {
    return "₹0";
  }
}
function rR(e) {
  if (!e) {
    return "—";
  }
  try {
    const t = new Date(e);
    if (Number.isNaN(t.getTime())) {
      return e;
    } else {
      return t.toLocaleDateString("en-IN", {
        day: "2-digit",
        month: "short",
        year: "numeric"
      });
    }
  } catch {
    return e;
  }
}
function _Component29({
  handlerNames: e = [],
  ownedSummary: t,
  onClose: r,
  onChanged: n
}) {
  const [a, i] = w.useState([]);
  const [l, c] = w.useState([]);
  const [o, u] = w.useState(true);
  const [d, f] = w.useState("");
  const [h, x] = w.useState("all");
  const [v, g] = w.useState("all");
  const [p, m] = w.useState("all");
  const [_, y] = w.useState(null);
  const [k, T] = w.useState(() => ({
    reference: e[0] || "",
    amount: "",
    category: "commission",
    note: "",
    date: new Date().toISOString().slice(0, 10)
  }));
  const [S, E] = w.useState(false);
  const b = w.useCallback(async () => {
    u(true);
    f("");
    try {
      const P = new URLSearchParams();
      if (v !== "all") {
        P.set("month", v);
      }
      const U = await (await fetch(`${ve}/handler-expenses?${P.toString()}`)).json();
      if (U.status === "ok") {
        i(U.expenses || []);
        c(U.available_months || []);
      } else {
        f(U.message || "Failed to load");
      }
    } catch (P) {
      f(P.message || "Network error");
    } finally {
      u(false);
    }
  }, [v]);
  w.useEffect(() => {
    b();
  }, [b]);
  w.useEffect(() => {
    function P(j) {
      if (j.key === "Escape" && !_) {
        if (r != null) {
          r();
        }
      }
    }
    document.addEventListener("keydown", P);
    return () => document.removeEventListener("keydown", P);
  }, [r, _]);
  const A = w.useMemo(() => {
    let P = a;
    if (h !== "all") {
      const j = h.toLowerCase();
      P = P.filter(U => (U.reference || "").toLowerCase() === j);
    }
    if (p !== "all") {
      P = P.filter(j => j.category === p);
    }
    return P;
  }, [a, h, p]);
  const O = Number(t == null ? undefined : t.owed) || 0;
  const L = w.useMemo(() => A.reduce((P, j) => P + (Number(j.amount) || 0), 0), [A]);
  const M = t != null ? Number(t.paid) || 0 : L;
  const C = O - M;
  const Y = {
    count: A.length
  };
  const J = w.useMemo(() => {
    const P = new Map();
    e.forEach(j => P.set(j.toLowerCase(), j));
    a.forEach(j => {
      const U = (j.reference || "").trim();
      if (U) {
        P.set(U.toLowerCase(), U);
      }
    });
    return [...P.values()].sort((j, U) => j.localeCompare(U));
  }, [a, e]);
  function G() {
    y(null);
    T({
      reference: h !== "all" ? h : J[0] || "",
      amount: "",
      category: "commission",
      note: "",
      date: new Date().toISOString().slice(0, 10)
    });
  }
  function ce(P) {
    y(P.id);
    T({
      reference: P.reference || "",
      amount: String(P.amount || ""),
      category: P.category || "other",
      note: P.note || "",
      date: P.date || new Date().toISOString().slice(0, 10)
    });
    requestAnimationFrame(() => {
      var j;
      if ((j = document.querySelector(".cand-allexp-form")) != null) {
        j.scrollIntoView({
          behavior: "smooth",
          block: "start"
        });
      }
    });
  }
  async function ee(P) {
    var U;
    if ((U = P == null ? undefined : P.preventDefault) != null) {
      U.call(P);
    }
    if (!k.reference.trim()) {
      f("Handler name is required");
      return;
    }
    const j = Number(k.amount);
    if (!Number.isFinite(j) || j <= 0) {
      f("Amount must be greater than zero");
      return;
    }
    E(true);
    f("");
    try {
      const W = {
        reference: k.reference.trim(),
        amount: j,
        category: k.category,
        note: k.note.trim(),
        date: k.date
      };
      const H = _ ? `${ve}/handler-expenses/${_}` : `${ve}/handler-expenses`;
      const pe = await (await fetch(H, {
        method: _ ? "PATCH" : "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(W)
      })).json();
      if (pe.status !== "ok") {
        f(pe.message || "Save failed");
        return;
      }
      G();
      b();
      if (n != null) {
        n();
      }
    } catch (W) {
      f(W.message || "Network error");
    } finally {
      E(false);
    }
  }
  async function B(P) {
    const j = Ex[P.category] || P.category || "payout";
    if (window.confirm(`Delete this ₹${P.amount.toLocaleString("en-IN")} ${j} for ${P.reference}?`)) {
      try {
        const W = await (await fetch(`${ve}/handler-expenses/${P.id}`, {
          method: "DELETE"
        })).json();
        if (W.status === "ok") {
          b();
          if (n != null) {
            n();
          }
        } else {
          f(W.message || "Delete failed");
        }
      } catch (U) {
        f(U.message || "Network error");
      }
    }
  }
  const Z = w.useMemo(() => [{
    value: "all",
    label: "All time"
  }, ...l.map(P => ({
    value: P.value,
    label: P.is_current ? `${P.label} · this month` : P.label
  }))], [l]);
  return <div className="cand-modal-backdrop" onClick={P => P.target === P.currentTarget && (r == null ? undefined : r())}><div className="cand-modal cand-modal--xl"><header className="cand-modal-header"><div><h3 className="cand-modal-title">Manage handler payouts</h3><p className="cand-modal-sub cand-payout-bar"><span className="cand-payout-chunk"><strong>{Y.count}</strong> entr{Y.count === 1 ? "y" : "ies"}</span><span className="cand-payout-chunk cand-payout-chunk--earn" title="Auto-computed: 50% of every rupee the client paid the business"><span className="cand-payout-pip" /> Owed (50%) <strong>{Jc(O)}</strong></span><span className="cand-payout-chunk cand-payout-chunk--ded" title="Every row in the payout ledger"><span className="cand-payout-pip" /> Paid out <strong>{Jc(M)}</strong></span><span className={`cand-payout-chunk ${C > 0 ? "cand-payout-chunk--net-pos" : C === 0 ? "cand-payout-chunk--net-zero" : "cand-payout-chunk--net-neg"}`}><span className="cand-payout-pip" />{C > 0 ? "Still owe " : C === 0 ? "Settled " : "Overpaid by "}<strong>{Jc(Math.abs(C))}</strong></span></p></div><button type="button" className="cand-modal-close" onClick={r} aria-label="Close">×</button></header><div className="cand-modal-body cand-modal-body--stack"><form className="cand-allexp-form cand-exp-form--payout" onSubmit={ee}><label className="cand-field"><span className="cand-field-label">Handler *</span><input className="cand-input" value={k.reference} onChange={P => T(j => ({
              ...j,
              reference: P.target.value
            }))} placeholder="e.g. Thrilok" list="cand-allexp-ref-list" required={true} /><datalist id="cand-allexp-ref-list">{J.map(P => <option value={P} key={P} />)}</datalist></label><label className="cand-field"><span className="cand-field-label">Amount (₹) *<span className="cand-exp-kind-tag cand-exp-kind-tag--payout">subtracted from what's owed</span></span><input className="cand-input" type="number" min="0" step="100" value={k.amount} onChange={P => T(j => ({
              ...j,
              amount: P.target.value
            }))} placeholder="5000" required={true} /></label><label className="cand-field"><span className="cand-field-label">Category</span><select className="cand-input" value={k.category} onChange={P => T(j => ({
              ...j,
              category: P.target.value
            }))}>{B0.map(P => <option value={P.value} key={P.value}>{P.label}</option>)}</select></label><label className="cand-field"><span className="cand-field-label">Date</span><input className="cand-input" type="date" value={k.date} onChange={P => T(j => ({
              ...j,
              date: P.target.value
            }))} /></label><label className="cand-field cand-field--span2"><span className="cand-field-label">Note</span><input className="cand-input" value={k.note} onChange={P => T(j => ({
              ...j,
              note: P.target.value
            }))} placeholder="e.g. May commission · taxi to client meeting" /></label><div className="cand-exp-form-actions cand-allexp-form-actions">{_ && <button type="button" className="cand-btn cand-btn--ghost" onClick={G}>Cancel edit</button>}<button type="submit" className="cand-btn cand-btn--primary" disabled={S}>{S ? "Saving…" : _ ? "Save changes" : "+ Log payout"}</button></div></form>{d && <div className="cand-modal-error">{d}</div>}<div className="cand-allexp-filters"><select className="cand-input cand-input--compact" value={h} onChange={P => x(P.target.value)} aria-label="Filter by handler"><option value="all">All handlers</option>{J.map(P => <option value={P} key={P}>{P}</option>)}</select><select className="cand-input cand-input--compact" value={v} onChange={P => g(P.target.value)} aria-label="Filter by month">{Z.map(P => <option value={P.value} key={P.value}>{P.label}</option>)}</select><select className="cand-input cand-input--compact" value={p} onChange={P => m(P.target.value)} aria-label="Filter by category"><option value="all">All categories</option>{B0.map(P => <option value={P.value} key={P.value}>{P.label}</option>)}</select>{(h !== "all" || v !== "all" || p !== "all") && <button type="button" className="cand-btn cand-btn--ghost cand-btn--xs" onClick={() => {
            x("all");
            g("all");
            m("all");
          }}>Clear filters</button>}</div>{o ? <div className="cand-exp-empty">Loading…</div> : A.length === 0 ? <div className="cand-exp-empty">No entries match the current filters. Use the form above to add the first one, or <button type="button" className="cand-link" onClick={() => {
            x("all");
            g("all");
            m("all");
          }}>clear filters</button>.</div> : <div className="cand-allexp-table-wrap"><table className="cand-allexp-table"><thead><tr><th>Handler</th><th>Amount</th><th>Category</th><th>Date</th><th>Note</th><th aria-label="actions" /></tr></thead><tbody>{A.map(P => <tr className={`cand-allexp-row cand-allexp-row--payout${_ === P.id ? " cand-allexp-row--editing" : ""}`} key={P.id}><td className="cand-allexp-ref">{P.reference}</td><td className="cand-allexp-amount cand-allexp-amount--payout">−{Jc(P.amount)}</td><td><span className={`cand-exp-cat cand-exp-cat--${P.category}`}>{Ex[P.category] || P.category}</span></td><td className="cand-allexp-date">{rR(P.date)}</td><td className="cand-allexp-note">{P.note || <em>—</em>}</td><td className="cand-allexp-actions"><button type="button" className="cand-btn cand-btn--ghost cand-btn--xs" onClick={() => ce(P)} title="Edit">✎</button><button type="button" className="cand-btn cand-btn--ghost cand-btn--xs cand-btn--danger-ghost" onClick={() => B(P)} title="Delete">🗑</button></td></tr>)}</tbody></table></div>}</div><footer className="cand-modal-footer"><button type="button" className="cand-btn cand-btn--ghost" onClick={r}>Close</button></footer></div></div>;
}
function At(e) {
  const t = Number(e) || 0;
  if (t) {
    if (Math.abs(t) < 100000) {
      return `₹${t.toLocaleString("en-IN")}`;
    } else {
      return `₹${(t / 100000).toFixed(t % 100000 === 0 ? 0 : 1)}L`;
    }
  } else {
    return "₹0";
  }
}
function _Component28({
  stats: e,
  scopeLabel: t,
  onClose: r,
  onManage: n
}) {
  const [a, i] = w.useState("table");
  w.useEffect(() => {
    function p(m) {
      if (m.key === "Escape") {
        if (r != null) {
          r();
        }
      }
    }
    document.addEventListener("keydown", p);
    return () => document.removeEventListener("keydown", p);
  }, [r]);
  const l = w.useMemo(() => {
    const p = ((e == null ? undefined : e.top_performers) || []).map(m => {
      const _ = Number(m.salary_total) || 0;
      const y = Number(m.commission_total ?? m.auto_earnings_total) || 0;
      const k = Number(m.auto_earnings_total) || 0;
      const T = Number(m.paid_out_total) || 0;
      const S = Number(m.net_payable) || 0;
      return {
        name: m.name,
        leads: Number(m.count) || 0,
        completed: Number(m.completed) || 0,
        revenue: Number(m.revenue) || 0,
        salary: _,
        commission: y,
        owed: k,
        paid: T,
        net: S
      };
    });
    p.sort((m, _) => m.net > 0 && _.net <= 0 ? -1 : _.net > 0 && m.net <= 0 ? 1 : m.net > 0 && _.net > 0 ? _.net - m.net : m.net === 0 && _.net === 0 ? _.owed - m.owed : _.net - m.net);
    return p;
  }, [e]);
  const c = (e == null ? undefined : e.handler_auto_earnings_total) ?? 0;
  const o = (e == null ? undefined : e.handler_salary_total) ?? 0;
  const u = (e == null ? undefined : e.handler_commission_total) ?? c - o;
  const d = (e == null ? undefined : e.handler_paid_out_total) ?? 0;
  const f = (e == null ? undefined : e.net_handler_payout) ?? c - d;
  const h = (e == null ? undefined : e.commission_pct) || 50;
  const x = l.filter(p => p.net > 0).length;
  const v = l.filter(p => p.net === 0).length;
  const g = l.filter(p => p.net < 0).length;
  return <div className="cand-modal-backdrop" onClick={p => p.target === p.currentTarget && (r == null ? undefined : r())}><div className="cand-modal cand-modal--xl cand-earn-modal" role="dialog" aria-modal="true"><header className="cand-modal-header"><div><h3 className="cand-modal-title">Everyone's earnings{t && <span className="cand-modal-scope"> · {t}</span>}</h3><p className="cand-modal-sub cand-payout-bar"><span className="cand-payout-chunk"><strong>{l.length}</strong> {l.length === 1 ? "handler" : "handlers"}</span><span className="cand-payout-chunk cand-payout-chunk--earn" title={`Salary base + ${h}% of every rupee collected`}><span className="cand-payout-pip" /> Owed <strong>{At(c)}</strong>{o > 0 && <em className="cand-earn-mix"> ({At(o)} salary + {At(u)} comm.)</em>}</span><span className="cand-payout-chunk cand-payout-chunk--ded" title="Every row already entered in the payout ledger"><span className="cand-payout-pip" /> Paid out <strong>{At(d)}</strong></span><span className={`cand-payout-chunk ${f > 0 ? "cand-payout-chunk--net-pos" : f === 0 ? "cand-payout-chunk--net-zero" : "cand-payout-chunk--net-neg"}`}><span className="cand-payout-pip" />{f > 0 ? "Still owe " : f === 0 ? "Settled " : "Overpaid by "}<strong>{At(Math.abs(f))}</strong></span></p></div><button type="button" className="cand-modal-close" onClick={r} aria-label="Close">×</button></header><div className="cand-earn-summary"><span className="cand-earn-summary-pill cand-earn-summary-pill--owe">{x} to pay</span><span className="cand-earn-summary-pill cand-earn-summary-pill--settled">{v} settled</span>{g > 0 && <span className="cand-earn-summary-pill cand-earn-summary-pill--over">{g} over-paid</span>}<span className="cand-earn-summary-spacer" /><div className="cand-earn-viewtoggle" role="tablist" aria-label="View as"><button type="button" role="tab" aria-selected={a === "table"} className={`cand-earn-viewtoggle-btn${a === "table" ? " is-active" : ""}`} onClick={() => i("table")}><span aria-hidden={true}>☰</span> Table</button><button type="button" role="tab" aria-selected={a === "chart"} className={`cand-earn-viewtoggle-btn${a === "chart" ? " is-active" : ""}`} onClick={() => i("chart")}><span aria-hidden={true}>📊</span> Chart</button></div></div>{a === "chart" ? <_Component24 rows={l} pct={h} /> : null}<div className="cand-earn-tablewrap" hidden={a !== "table"}>{l.length === 0 ? <div className="cand-exp-empty">No handlers yet — assign at least one candidate to a reference and they'll appear here.</div> : <table className="cand-earn-table"><thead><tr><th className="cand-earn-col-rank">#</th><th className="cand-earn-col-name">Handler</th><th className="cand-earn-col-leads" title="Leads / completed">Leads</th><th className="cand-earn-col-money" title="Fixed monthly base salary">Salary</th><th className="cand-earn-col-money" title={`${h}% of every rupee the client paid`}>Commission</th><th className="cand-earn-col-money" title="Salary + Commission">Owed</th><th className="cand-earn-col-money" title="From the payout ledger">Paid out</th><th className="cand-earn-col-status">Status</th></tr></thead><tbody>{l.map((p, m) => {
              const _ = p.net > 0 ? "cand-earn-row--owe" : p.net === 0 ? "cand-earn-row--settled" : "cand-earn-row--over";
              return <tr className={`cand-earn-row ${_}`} key={p.name}><td className="cand-earn-col-rank">{m + 1}</td><td className="cand-earn-col-name"><span className="cand-earn-name">{p.name}</span>{p.revenue > 0 && <span className="cand-earn-rev" title="Total client revenue this handler generated">{At(p.revenue)} collected</span>}</td><td className="cand-earn-col-leads"><span className="cand-earn-leads">{p.leads}{p.completed > 0 && <em className="cand-earn-leads-done">· {p.completed} done</em>}</span></td><td className="cand-earn-col-money">{p.salary > 0 ? <span className="cand-earn-chip cand-earn-chip--salary">{At(p.salary)}</span> : <span className="cand-earn-dash">—</span>}</td><td className="cand-earn-col-money">{p.commission > 0 ? <span className="cand-earn-chip cand-earn-chip--commission">{At(p.commission)}</span> : <span className="cand-earn-dash">—</span>}</td><td className="cand-earn-col-money cand-earn-col-money--owed"><strong>{At(p.owed)}</strong></td><td className="cand-earn-col-money">{p.paid > 0 ? <span className="cand-earn-chip cand-earn-chip--paid">{At(p.paid)}</span> : <span className="cand-earn-dash">—</span>}</td><td className="cand-earn-col-status">{p.net > 0 ? <span className="cand-earn-status cand-earn-status--owe">Pay <strong>{At(p.net)}</strong></span> : p.net === 0 ? <span className="cand-earn-status cand-earn-status--settled">✓ Settled</span> : <span className="cand-earn-status cand-earn-status--over">Recover <strong>{At(Math.abs(p.net))}</strong></span>}</td></tr>;
            })}</tbody><tfoot><tr className="cand-earn-foot"><td colSpan={3}>Total</td><td className="cand-earn-col-money">{o > 0 ? <span className="cand-earn-chip cand-earn-chip--salary">{At(o)}</span> : "—"}</td><td className="cand-earn-col-money"><span className="cand-earn-chip cand-earn-chip--commission">{At(u)}</span></td><td className="cand-earn-col-money cand-earn-col-money--owed"><strong>{At(c)}</strong></td><td className="cand-earn-col-money">{d > 0 ? <span className="cand-earn-chip cand-earn-chip--paid">{At(d)}</span> : "—"}</td><td className="cand-earn-col-status"><span className={`cand-earn-status ${f > 0 ? "cand-earn-status--owe" : f === 0 ? "cand-earn-status--settled" : "cand-earn-status--over"}`}>{f > 0 ? <s.Fragment>Pay <strong>{At(f)}</strong></s.Fragment> : f === 0 ? "✓ Settled" : <s.Fragment>Recover <strong>{At(Math.abs(f))}</strong></s.Fragment>}</span></td></tr></tfoot></table>}</div><footer className="cand-earn-footer"><p className="cand-earn-foot-help">Owed amounts are auto-computed from candidate payments ({h}% of every rupee collected) plus any fixed monthly salary. Use the ledger below to log actual payouts.</p><div className="cand-earn-foot-actions"><button type="button" className="cand-btn cand-btn--ghost" onClick={r}>Close</button>{n && <button type="button" className="cand-btn cand-btn--primary" onClick={() => {
            if (r != null) {
              r();
            }
            n();
          }}>Manage payouts ledger →</button>}</div></footer></div></div>;
}
function _Component24({
  rows: e,
  pct: t
}) {
  const r = Math.max(1, ...e.map(n => Math.max(n.owed, n.paid)));
  if (e.length) {
    return <div className="cand-earn-chart" role="img" aria-label="Earnings by handler"><div className="cand-earn-chart-legend"><span className="cand-earn-chart-legend-item"><span className="cand-earn-chart-swatch cand-earn-chart-swatch--salary" />Salary (base)</span><span className="cand-earn-chart-legend-item"><span className="cand-earn-chart-swatch cand-earn-chart-swatch--commission" />Commission ({t}%)</span><span className="cand-earn-chart-legend-item"><span className="cand-earn-chart-swatch cand-earn-chart-swatch--paid" />Already paid out</span></div><ul className="cand-earn-chart-list">{e.map(n => {
          const a = n.owed / r * 100;
          const i = n.paid / r * 100;
          const l = n.owed > 0 ? n.salary / n.owed * a : 0;
          const c = n.owed > 0 ? n.commission / n.owed * a : 0;
          return <li className="cand-earn-chart-row" key={n.name}><div className="cand-earn-chart-name"><strong>{n.name}</strong><span className={`cand-earn-chart-net ${n.net > 0 ? "cand-earn-chart-net--owe" : n.net === 0 ? "cand-earn-chart-net--settled" : "cand-earn-chart-net--over"}`}>{n.net > 0 ? `Pay ${At(n.net)}` : n.net === 0 ? "✓ Settled" : `Recover ${At(Math.abs(n.net))}`}</span></div><div className="cand-earn-chart-bars"><div className="cand-earn-chart-bar" aria-label="Owed breakdown"><span className="cand-earn-chart-bar-label">Owed</span><div className="cand-earn-chart-bar-track">{l > 0 && <span className="cand-earn-chart-bar-fill cand-earn-chart-bar-fill--salary" style={{
                    width: `${l}%`
                  }} title={`Salary ${At(n.salary)}`} />}{c > 0 && <span className="cand-earn-chart-bar-fill cand-earn-chart-bar-fill--commission" style={{
                    width: `${c}%`
                  }} title={`Commission ${At(n.commission)}`} />}</div><span className="cand-earn-chart-bar-value">{At(n.owed)}</span></div><div className="cand-earn-chart-bar" aria-label="Paid out"><span className="cand-earn-chart-bar-label cand-earn-chart-bar-label--muted">Paid</span><div className="cand-earn-chart-bar-track">{i > 0 && <span className="cand-earn-chart-bar-fill cand-earn-chart-bar-fill--paid" style={{
                    width: `${i}%`
                  }} title={`Paid out ${At(n.paid)}`} />}</div><span className="cand-earn-chart-bar-value cand-earn-chart-bar-value--muted">{At(n.paid)}</span></div></div></li>;
        })}</ul></div>;
  } else {
    return <div className="cand-earn-chart cand-earn-chart--empty">Nothing to plot yet — add candidates to populate this chart.</div>;
  }
}
function jx(e) {
  const t = Number(e) || 0;
  if (t < 1024) {
    return `${t} B`;
  } else if (t < 1048576) {
    return `${(t / 1024).toFixed(0)} KB`;
  } else {
    return `${(t / 1048576).toFixed(1)} MB`;
  }
}
function Sx(e) {
  if (!e) {
    return "";
  }
  try {
    return fmtIstDt(e);
  } catch {
    return "";
  }
}
function _Component31({
  candidate: e,
  onClose: t,
  onEdit: r
}) {
  const [n, a] = w.useState(null);
  const i = Array.isArray(e == null ? undefined : e.proofs) ? e.proofs : [];
  w.useEffect(() => {
    function u(d) {
      if (d.key === "Escape") {
        if (n) {
          a(null);
        } else if (t != null) {
          t();
        }
      }
    }
    document.addEventListener("keydown", u);
    return () => document.removeEventListener("keydown", u);
  }, [n, t]);
  const l = Number(e == null ? undefined : e.expected_payment) || 20000;
  const c = Number(e == null ? undefined : e.payment) || 0;
  const o = Math.max(0, l - c);
  return <div className="cand-modal-backdrop" onClick={u => u.target === u.currentTarget && (t == null ? undefined : t())}><div className="cand-modal cand-modal--wide"><header className="cand-modal-header"><div><h3 className="cand-modal-title">Payment proofs · <span className="cand-handler-name">{e == null ? undefined : e.name}</span></h3><p className="cand-modal-sub cand-payout-bar"><span className="cand-payout-chunk cand-payout-chunk--earn"><span className="cand-payout-pip" /> Received <strong>₹{c.toLocaleString("en-IN")}</strong></span><span className="cand-payout-chunk">of <strong>₹{l.toLocaleString("en-IN")}</strong> expected</span>{o > 0 && <span className="cand-payout-chunk cand-payout-chunk--net-neg"><span className="cand-payout-pip" /> Balance <strong>₹{o.toLocaleString("en-IN")}</strong></span>}<span className="cand-payout-chunk"><strong>{i.length}</strong> screenshot{i.length === 1 ? "" : "s"} on file</span></p></div><button type="button" className="cand-modal-close" onClick={t} aria-label="Close">×</button></header><div className="cand-modal-body cand-modal-body--stack">{i.length === 0 ? <div className="cand-exp-empty">No payment screenshots attached to this candidate yet.</div> : <ul className="cand-proofs-grid">{i.map(u => <li className="cand-proof-card" key={u.id}><button type="button" className="cand-proof-thumb" onClick={() => a(u)} aria-label={`Preview ${u.note || "payment proof"}`}><img src={`${ve}${u.url}`} alt={u.note || u.original_name || "payment proof"} loading="lazy" /></button><div className="cand-proof-meta"><div className="cand-proof-note cand-proof-note--readonly">{u.note || <em>no caption</em>}</div><div className="cand-proof-sub"><span>{Sx(u.uploaded_at)}</span><span>·</span><span>{jx(u.size)}</span></div><a href={`${ve}${u.url}`} download={u.original_name || u.filename} className="cand-btn cand-btn--ghost cand-btn--xs cand-proof-download" onClick={d => d.stopPropagation()}>⤓ Download</a></div></li>)}</ul>}</div><footer className="cand-modal-footer">{r && <button type="button" className="cand-btn cand-btn--ghost" onClick={() => {
          if (t != null) {
            t();
          }
          r(e);
        }} title="Open the full candidate edit form (lets you add or delete proofs)">Edit candidate →</button>}<button type="button" className="cand-btn cand-btn--primary" onClick={t}>Close</button></footer>{n && <div className="cand-proof-lightbox" onClick={() => a(null)} role="dialog" aria-label="Payment proof preview"><button type="button" className="cand-proof-lightbox-close" onClick={() => a(null)} aria-label="Close preview">×</button><img src={`${ve}${n.url}`} alt={n.note || n.original_name} onClick={u => u.stopPropagation()} /><div className="cand-proof-lightbox-caption" onClick={u => u.stopPropagation()}>{n.note && <strong>{n.note}</strong>}<span>{Sx(n.uploaded_at)} · {jx(n.size)}</span><a href={`${ve}${n.url}`} download={n.original_name || n.filename} className="cand-btn cand-btn--ghost cand-btn--xs">Download</a></div></div>}</div></div>;
}
function _Component32({
  open: e,
  title: t,
  message: r,
  onVerified: n,
  onCancel: a
}) {
  const [i, l] = w.useState("");
  const [c, o] = w.useState("");
  const [u, d] = w.useState(false);
  const f = w.useRef(null);
  w.useEffect(() => {
    if (!e) {
      return;
    }
    l("");
    o("");
    const x = setTimeout(() => {
      var v;
      if ((v = f.current) == null) {
        return undefined;
      } else {
        return v.focus();
      }
    }, 50);
    return () => clearTimeout(x);
  }, [e]);
  if (!e) {
    return null;
  }
  async function h(x) {
    var v;
    if ((v = x == null ? undefined : x.preventDefault) != null) {
      v.call(x);
    }
    if (!i.trim()) {
      o("Enter the admin password");
      return;
    }
    d(true);
    o("");
    try {
      const g = await fetch(`${ve}/auth/verify-admin`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          password: i
        })
      });
      const p = await g.json().catch(() => ({}));
      if (!g.ok) {
        o(p.detail || p.message || "Incorrect password");
        return;
      }
      if (n != null) {
        n();
      }
    } catch (g) {
      o(g.message || "Could not verify password");
    } finally {
      d(false);
    }
  }
  return <div className="modal-backdrop confirm-backdrop" onClick={u ? undefined : a} role="presentation"><div className="cand-modal cand-modal--narrow" role="dialog" aria-modal="true" aria-labelledby="admin-pw-title" onClick={x => x.stopPropagation()}><header className="cand-modal-header"><h3 className="cand-modal-title" id="admin-pw-title">{t || "Admin password required"}</h3><p className="cand-modal-sub">{r || "Enter the main dashboard admin password to continue."}</p></header><form className="cand-modal-body" onSubmit={h}><label className="cand-field"><span className="cand-field-label">Password</span><input ref={f} className="cand-input" type="password" autoComplete="current-password" value={i} onChange={x => l(x.target.value)} disabled={u} /></label>{c && <p className="cand-error" role="alert">{c}</p>}<footer className="cand-modal-footer"><button type="button" className="cand-btn cand-btn--ghost" onClick={a} disabled={u}>Cancel</button><button type="submit" className="cand-btn cand-btn--primary" disabled={u}>{u ? "Checking…" : "Unlock"}</button></footer></form></div></div>;
}
const E_ = [{
  value: "commission",
  label: "Commission payout"
}, {
  value: "travel",
  label: "Travel / fuel"
}, {
  value: "food",
  label: "Food / meals"
}, {
  value: "gym",
  label: "Gym / health"
}, {
  value: "equipment",
  label: "Equipment"
}, {
  value: "marketing",
  label: "Marketing"
}, {
  value: "software",
  label: "Software / tools"
}, {
  value: "other",
  label: "Other"
}];
const Tx = Object.fromEntries(E_.map(e => [e.value, e.label]));
function Qc(e) {
  const t = Number(e) || 0;
  if (t) {
    return `₹${t.toLocaleString("en-IN")}`;
  } else {
    return "₹0";
  }
}
function oR(e) {
  if (!e) {
    return "—";
  }
  try {
    const t = new Date(e);
    if (Number.isNaN(t.getTime())) {
      return e;
    } else {
      return t.toLocaleDateString("en-IN", {
        day: "2-digit",
        month: "short",
        year: "numeric"
      });
    }
  } catch {
    return e;
  }
}
function _Component30({
  handler: e,
  onClose: t,
  onChanged: r
}) {
  var J;
  const [n, a] = w.useState([]);
  const [i, l] = w.useState(0);
  const [c, o] = w.useState(true);
  const [u, d] = w.useState("");
  const [f, h] = w.useState("all");
  const [x, v] = w.useState([]);
  const [g, p] = w.useState(null);
  const [m, _] = w.useState(() => ({
    reference: (e == null ? undefined : e.name) || "",
    amount: "",
    category: "commission",
    note: "",
    date: new Date().toISOString().slice(0, 10)
  }));
  const [y, k] = w.useState(false);
  const T = w.useCallback(async () => {
    if (e != null && e.name) {
      o(true);
      d("");
      try {
        const G = new URLSearchParams();
        G.set("reference", e.name);
        if (f !== "all") {
          G.set("month", f);
        }
        const ee = await (await fetch(`${ve}/handler-expenses?${G.toString()}`)).json();
        if (ee.status === "ok") {
          a(ee.expenses || []);
          l(ee.total || 0);
          v(ee.available_months || []);
        } else {
          d(ee.message || "Failed to load");
        }
      } catch (G) {
        d(G.message || "Network error");
      } finally {
        o(false);
      }
    }
  }, [e == null ? undefined : e.name, f]);
  w.useEffect(() => {
    T();
  }, [T]);
  w.useEffect(() => {
    function G(ce) {
      if (ce.key === "Escape") {
        if (t != null) {
          t();
        }
      }
    }
    document.addEventListener("keydown", G);
    return () => document.removeEventListener("keydown", G);
  }, [t]);
  function S() {
    p(null);
    _({
      reference: (e == null ? undefined : e.name) || "",
      amount: "",
      category: "commission",
      note: "",
      date: new Date().toISOString().slice(0, 10)
    });
  }
  function E(G) {
    p(G);
    _({
      reference: G.reference || (e == null ? undefined : e.name) || "",
      amount: String(G.amount || ""),
      category: G.category || "other",
      note: G.note || "",
      date: G.date || new Date().toISOString().slice(0, 10)
    });
  }
  async function b(G) {
    var ee;
    if ((ee = G == null ? undefined : G.preventDefault) != null) {
      ee.call(G);
    }
    if (!m.reference.trim()) {
      d("Handler name is required");
      return;
    }
    const ce = Number(m.amount);
    if (!Number.isFinite(ce) || ce <= 0) {
      d("Amount must be greater than zero");
      return;
    }
    k(true);
    d("");
    try {
      const B = {
        reference: m.reference.trim(),
        amount: ce,
        category: m.category,
        note: m.note.trim(),
        date: m.date
      };
      const Z = g ? `${ve}/handler-expenses/${g.id}` : `${ve}/handler-expenses`;
      const U = await (await fetch(Z, {
        method: g ? "PATCH" : "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(B)
      })).json();
      if (U.status !== "ok") {
        d(U.message || "Save failed");
        return;
      }
      S();
      T();
      if (r != null) {
        r();
      }
    } catch (B) {
      d(B.message || "Network error");
    } finally {
      k(false);
    }
  }
  async function A(G) {
    if (window.confirm(`Delete this ₹${G.amount.toLocaleString("en-IN")} ${Tx[G.category] || G.category} expense?`)) {
      try {
        const ee = await (await fetch(`${ve}/handler-expenses/${G.id}`, {
          method: "DELETE"
        })).json();
        if (ee.status === "ok") {
          T();
          if (r != null) {
            r();
          }
        } else {
          d(ee.message || "Delete failed");
        }
      } catch (ce) {
        d(ce.message || "Network error");
      }
    }
  }
  const O = w.useMemo(() => [{
    value: "all",
    label: "All time"
  }, ...x.map(G => ({
    value: G.value,
    label: G.is_current ? `${G.label} · this month` : G.label
  }))], [x]);
  const L = w.useMemo(() => n.reduce((G, ce) => G + (Number(ce.amount) || 0), 0), [n]);
  const M = Number(e == null ? undefined : e.auto_earnings_total) || Number(e == null ? undefined : e.earnings_total) || 0;
  const C = Number(e == null ? undefined : e.commission_pct) || 50;
  const Y = M - L;
  return <div className="cand-modal-backdrop" onClick={G => G.target === G.currentTarget && (t == null ? undefined : t())}><div className="cand-modal cand-modal--wide"><header className="cand-modal-header"><div><h3 className="cand-modal-title">Payout ledger · <span className="cand-handler-name">{(e == null ? undefined : e.name) || "Handler"}</span></h3><p className="cand-modal-sub cand-payout-bar">{(e == null ? undefined : e.count) != null && <span className="cand-payout-chunk"><strong>{e.count}</strong> lead{e.count === 1 ? "" : "s"}</span>}<span className="cand-payout-chunk cand-payout-chunk--earn" title={`${C}% of every rupee the client paid the business`}><span className="cand-payout-pip" /> Owed ({C}%) <strong>{Qc(M)}</strong></span><span className="cand-payout-chunk cand-payout-chunk--ded" title="Sum of every row in this ledger"><span className="cand-payout-pip" /> Paid out <strong>{Qc(L)}</strong></span><span className={`cand-payout-chunk ${Y > 0 ? "cand-payout-chunk--net-pos" : Y === 0 ? "cand-payout-chunk--net-zero" : "cand-payout-chunk--net-neg"}`}><span className="cand-payout-pip" />{Y > 0 ? "Still owe " : Y === 0 ? "Settled " : "Overpaid by "}<strong>{Qc(Math.abs(Y))}</strong></span>{f !== "all" && <span className="cand-payout-chunk cand-payout-chunk--muted">scope: {((J = x.find(G => G.value === f)) == null ? undefined : J.label) || f}</span>}</p></div><button type="button" className="cand-modal-close" onClick={t} aria-label="Close">×</button></header><div className="cand-modal-body cand-modal-body--stack"><form className="cand-exp-form cand-exp-form--payout" onSubmit={b}><label className="cand-field cand-exp-field--amount"><span className="cand-field-label">Amount (₹) *<span className="cand-exp-kind-tag cand-exp-kind-tag--payout">subtracted from what's owed</span></span><input className="cand-input" type="number" min="0" step="100" value={m.amount} onChange={G => _(ce => ({
              ...ce,
              amount: G.target.value
            }))} placeholder="5000" required={true} /></label><label className="cand-field cand-exp-field--cat"><span className="cand-field-label">Category</span><select className="cand-input" value={m.category} onChange={G => _(ce => ({
              ...ce,
              category: G.target.value
            }))}>{E_.map(G => <option value={G.value} key={G.value}>{G.label}</option>)}</select></label><label className="cand-field cand-exp-field--date"><span className="cand-field-label">Date</span><input className="cand-input" type="date" value={m.date} onChange={G => _(ce => ({
              ...ce,
              date: G.target.value
            }))} /></label><label className="cand-field cand-exp-field--note"><span className="cand-field-label">Note</span><input className="cand-input" value={m.note} onChange={G => _(ce => ({
              ...ce,
              note: G.target.value
            }))} placeholder="e.g. May referral bonus · taxi to client meeting" /></label><div className="cand-exp-form-actions">{g && <button type="button" className="cand-btn cand-btn--ghost" onClick={S}>Cancel edit</button>}<button type="submit" className="cand-btn cand-btn--primary" disabled={y}>{y ? "Saving…" : g ? "Save changes" : "+ Log payout"}</button></div></form>{u && <div className="cand-modal-error">{u}</div>}<div className="cand-exp-list-header"><span className="cand-field-label">Ledger<span className="cand-exp-count">{n.length}</span></span><select className="cand-input cand-input--compact" value={f} onChange={G => h(G.target.value)} aria-label="Filter by month">{O.map(G => <option value={G.value} key={G.value}>{G.label}</option>)}</select></div>{c ? <div className="cand-exp-empty">Loading…</div> : n.length === 0 ? <div className="cand-exp-empty">No expenses logged{f !== "all" ? " for this month" : ""}. Use the form above to add the first one.</div> : <ul className="cand-exp-list">{n.map(G => <li className={`cand-exp-row${(g == null ? undefined : g.id) === G.id ? " cand-exp-row--editing" : ""}`} key={G.id}><div className="cand-exp-row-main"><span className="cand-exp-amount">{Qc(G.amount)}</span><span className={`cand-exp-cat cand-exp-cat--${G.category}`}>{Tx[G.category] || G.category}</span><span className="cand-exp-date">{oR(G.date)}</span></div>{G.note && <div className="cand-exp-note">{G.note}</div>}<div className="cand-exp-row-actions"><button type="button" className="cand-btn cand-btn--ghost cand-btn--xs" onClick={() => E(G)} title="Edit">✎</button><button type="button" className="cand-btn cand-btn--ghost cand-btn--xs cand-btn--danger-ghost" onClick={() => A(G)} title="Delete">🗑</button></div></li>)}</ul>}</div><footer className="cand-modal-footer"><button type="button" className="cand-btn cand-btn--ghost" onClick={t}>Close</button></footer></div></div>;
}
const dR = [{
  value: "all",
  label: "All stages"
}, {
  value: "in_progress",
  label: "In progress"
}, {
  value: "completed",
  label: "Completed"
}, {
  value: "fail",
  label: "Failed"
}, {
  value: "dropped",
  label: "Dropped"
}];
function fR(e) {
  return {
    completed: {
      label: "Completed",
      cls: "cand-badge--good"
    },
    in_progress: {
      label: "In progress",
      cls: "cand-badge--info"
    },
    fail: {
      label: "Failed",
      cls: "cand-badge--bad"
    },
    dropped: {
      label: "Dropped",
      cls: "cand-badge--muted"
    }
  }[e] || {
    label: e || "—",
    cls: "cand-badge--muted"
  };
}
function Cx(e) {
  const t = Number(e) || 0;
  if (t) {
    return `₹${t.toLocaleString("en-IN")}`;
  } else {
    return "—";
  }
}
function Ax(e) {
  const t = Number(e) || 0;
  if (t) {
    if (t < 1000) {
      return `₹${t}`;
    } else if (t < 100000) {
      return `₹${(t / 1000).toFixed(t % 1000 === 0 ? 0 : 1)}k`;
    } else {
      return `₹${(t / 100000).toFixed(t % 100000 === 0 ? 0 : 1)}L`;
    }
  } else {
    return "₹0";
  }
}
function _Component27({
  row: e,
  onViewProofs: t
}) {
  const r = Number(e.expected_payment) || 20000;
  const n = Number(e.payment) || 0;
  const a = Math.max(0, r - n);
  const i = e.payment_status || (n <= 0 ? "unpaid" : n >= r ? "paid" : "partial");
  const l = Number(e.proof_count) || (Array.isArray(e.proofs) ? e.proofs.length : 0);
  const c = l > 0 ? <button type="button" className="cand-pay-proofs cand-pay-proofs--btn" onClick={o => {
    o.stopPropagation();
    if (t != null) {
      t(e);
    }
  }} title={`View ${l} payment screenshot${l === 1 ? "" : "s"}`}><span aria-hidden={true}>📎</span> {l}<span className="cand-pay-proofs-cta">View</span></button> : null;
  if (i === "paid") {
    return <div className="cand-cell-money cand-pay"><span className="cand-pay-amount">{Cx(n)}</span><span className="cand-pay-pillrow"><span className="cand-pay-pill cand-pay-pill--paid">Paid</span>{c}</span></div>;
  } else {
    return <div className="cand-cell-money cand-pay"><span className="cand-pay-amount">{n > 0 ? Cx(n) : <span className="cand-pay-zero">₹0</span>}<span className="cand-pay-expected"> / {Ax(r)}</span></span><span className="cand-pay-pillrow"><span className={`cand-pay-pill cand-pay-pill--${i === "unpaid" ? "unpaid" : "partial"}`} title={e.follow_up || ""}>{Ax(a)} due</span>{c}</span></div>;
  }
}
function pR(e) {
  if (!e) {
    return "—";
  }
  try {
    const t = new Date(e);
    if (Number.isNaN(t.getTime())) {
      return e;
    } else {
      return t.toLocaleDateString("en-IN", {
        day: "2-digit",
        month: "short",
        year: "numeric"
      });
    }
  } catch {
    return e;
  }
}
function mR() {
  const e = new Date();
  return `${e.getUTCFullYear()}-${String(e.getUTCMonth() + 1).padStart(2, "0")}`;
}
export function CandidatesPanel() {
  const {
    role: e,
    reference: t,
    enabled: r
  } = wu();
  const n = r && e === "handler";
  const a = !r || e === "admin";
  const [i, l] = w.useState([]);
  const [c, o] = w.useState(null);
  const [u, d] = w.useState(null);
  const [f, h] = w.useState(true);
  const [x, v] = w.useState("");
  const [g, p] = w.useState("all");
  const [m, _] = w.useState(() => mR());
  const [y, k] = w.useState(false);
  const [T, S] = w.useState("all");
  const [E, b] = w.useState("");
  const [A, O] = w.useState("");
  const [L, M] = w.useState(false);
  const [C, Y] = w.useState(null);
  const [J, G] = w.useState(false);
  const [ce, ee] = w.useState(false);
  const [B, Z] = w.useState(null);
  const [P, j] = w.useState(null);
  const [ro, setRo] = w.useState(false);
  const {
    confirm: U
  } = nc();
  const {
    gate: W,
    closeGate: H,
    runProtected: re
  } = cR();
  const ue = () => re(() => G(true), {
    title: "Manage expenses",
    message: "Enter the admin password to view or edit handler payouts and expenses."
  });
  const pe = () => {
    if (n) {
      ee(true);
      return;
    }
    re(() => ee(true), {
      title: "Handler payouts",
      message: "Enter the admin password to open the full earnings and payout board."
    });
  };
  const me = ge => re(() => j(ge), {
    title: "Edit handler payout",
    message: "Enter the admin password to log or edit payouts for this handler."
  });
  w.useEffect(() => {
    if (n && t) {
      S(t);
    }
  }, [n, t]);
  w.useEffect(() => {
    const ge = setTimeout(() => O(E.trim()), 250);
    return () => clearTimeout(ge);
  }, [E]);
  const fe = w.useCallback(async () => {
    h(true);
    v("");
    try {
      const effectiveRef = T !== "all" ? T : n && t ? t : null;
      const ge = new URLSearchParams();
      if (g !== "all") {
        ge.set("stage", g);
      }
      if (m !== "all") {
        ge.set("month", m);
      }
      if (y) {
        ge.set("pending_only", "1");
      }
      if (effectiveRef) {
        ge.set("reference", effectiveRef);
      }
      if (A) {
        ge.set("search", A);
      }
      const Ge = new URLSearchParams();
      if (m !== "all") {
        Ge.set("month", m);
      }
      if (effectiveRef) {
        Ge.set("reference", effectiveRef);
      }
      const Ze = [fetch(`${ve}/candidates?${ge.toString()}`), fetch(`${ve}/candidates/stats?${Ge.toString()}`)];
      if (m !== "all" && a) {
        Ze.push(fetch(`${ve}/candidates/stats`));
      }
      const [Be, Xe, je] = await Promise.all(Ze);
      const Tt = await Be.json();
      const ot = await Xe.json();
      const xt = je ? await je.json() : ot;
      if (Tt.status === "ok") {
        l(Tt.candidates || []);
      } else {
        v(Tt.message || "Failed to load candidates");
      }
      if (ot.status === "ok") {
        o(ot.stats);
      }
      if ((xt == null ? undefined : xt.status) === "ok") {
        d(xt.stats);
      }
    } catch (ge) {
      v(ge.message || "Network error");
    } finally {
      h(false);
    }
  }, [g, m, y, T, A, a, n, t]);
  w.useEffect(() => {
    fe();
  }, [fe]);
  const q = () => {
    Y(null);
    M(true);
  };
  const I = ge => {
    Y(ge);
    M(true);
  };
  const Oe = () => {
    M(false);
    Y(null);
  };
  async function Re(ge) {
    const Ge = C ? `${ve}/candidates/${C.id}` : `${ve}/candidates`;
    const Xe = await (await fetch(Ge, {
      method: C ? "PATCH" : "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(ge)
    })).json();
    if (Xe.status !== "ok") {
      throw new Error(Xe.message || "Save failed");
    }
    Oe();
    fe();
  }
  async function Pe(ge) {
    if (!(await U({
      title: `Delete ${ge.name}?`,
      message: "This removes the candidate row permanently. Cannot be undone.",
      confirmLabel: "Delete",
      variant: "danger"
    }))) {
      return;
    }
    const Be = await (await fetch(`${ve}/candidates/${ge.id}`, {
      method: "DELETE"
    })).json();
    if (Be.status === "ok") {
      fe();
    } else {
      v(Be.message || "Delete failed");
    }
  }
  const De = i.length;
  const ye = w.useMemo(() => c ? Object.values(c.by_stage || {}).reduce((ge, Ge) => ge + Ge, 0) : 0, [c]);
  const Le = w.useMemo(() => {
    var Ge;
    const ge = ((Ge = u || c) == null ? undefined : Ge.available_months) || [];
    return [{
      value: "all",
      label: "All time"
    }, ...ge.map(Ze => ({
      value: Ze.value,
      label: Ze.is_current ? `${Ze.label} · this month` : Ze.label
    }))];
  }, [u, c]);
  const $e = w.useMemo(() => {
    if (m === "all") {
      return null;
    }
    const ge = Le.find(Ge => Ge.value === m);
    if (ge) {
      return ge.label.replace(" · this month", "");
    } else {
      return m;
    }
  }, [m, Le]);
  const st = w.useMemo(() => {
    const ge = new Map();
    for (const Be of (c == null ? undefined : c.top_performers) || []) {
      const Xe = (Be.name || "").trim();
      if (Xe) {
        ge.set(Xe.toLowerCase(), {
          name: Xe,
          count: Be.count || 0
        });
      }
    }
    const Ge = new Map();
    for (const Be of (u == null ? undefined : u.top_performers) || (c == null ? undefined : c.top_performers) || []) {
      const Xe = (Be.name || "").trim();
      if (!Xe) {
        continue;
      }
      const je = Xe.toLowerCase();
      const Tt = ge.get(je);
      Ge.set(je, {
        name: Xe,
        count: Tt ? Tt.count : 0
      });
    }
    const Ze = Array.from(Ge.values());
    Ze.sort((Be, Xe) => Xe.count !== Be.count ? Xe.count - Be.count : Be.name.localeCompare(Xe.name));
    return [{
      value: "all",
      label: "All handlers"
    }, ...Ze.map(Be => ({
      value: Be.name,
      label: Be.count > 0 ? `${Be.name} · ${Be.count}` : Be.name
    }))];
  }, [c, u]);
  return <div className="cand-page"><header className="cand-header"><div className="cand-header-titles"><h2 className="cand-title">Candidates</h2><p className="cand-subtitle">{n ? `Your referred candidates and earnings${t ? ` — ${t}` : ""}.` : "Tracker for every profile you take on — replaces the old Profiles list update Form sheet."}</p></div><div className="cand-header-actions"><button type="button" className="cand-btn cand-btn--ghost" onClick={() => setRo(true)} title="View all in-progress candidates grouped by technology">Active list</button><button type="button" className="cand-btn cand-btn--ghost" onClick={() => triggerRosterDownload({ month: "all", reference: T })} title="Download CSV of all active (in-progress) candidates">Download active CSV</button>{a && <button type="button" className="cand-btn cand-btn--ghost" onClick={ue} title="View, edit, or delete every handler earning + deduction (admin password required)"><span aria-hidden={true}>₹</span> Manage expenses{((c == null ? undefined : c.handler_deductions_total) > 0 || (c == null ? undefined : c.handler_earnings_total) > 0) && <span className="cand-btn-badge">{(c.handler_earnings_total || 0) + (c.handler_deductions_total || 0) > 0 ? "●" : ""}</span>}</button>}<button type="button" className="cand-btn cand-btn--primary" onClick={q}><span aria-hidden={true}>＋</span> Add candidate</button></div></header>{c && <J8 stats={c} scopeLabel={$e} onPayoutsClick={pe} handlerView={n} handlerName={t} scopeReference={T !== "all" ? T : n ? t : null} />}{c && <_Component26 stats={c} month={m} onMonthChange={_} monthOptions={Le} onExpensesChanged={fe} onShowEarnings={a ? pe : undefined} onEditPayout={a ? me : undefined} handlerView={n} handlerName={t} scopeReference={T !== "all" ? T : n ? t : null} />}<div className="cand-toolbar" role="region" aria-label="Candidate filters"><input className="cand-input cand-input--search" placeholder="Search name, tech, reference, phone, notes…" value={E} onChange={ge => b(ge.target.value)} /><select className="cand-input" value={m} onChange={ge => _(ge.target.value)} aria-label="Filter by month">{Le.map(ge => <option value={ge.value} key={ge.value}>{ge.label}</option>)}</select><select className="cand-input" value={g} onChange={ge => p(ge.target.value)}>{dR.map(ge => <option value={ge.value} key={ge.value}>{ge.label}</option>)}</select>{a && <select className={`cand-input${T !== "all" ? " cand-input--active" : ""}`} value={T} onChange={ge => S(ge.target.value)} aria-label="Filter by handler / reference" title="Show only candidates referred by this handler">{st.map(ge => <option value={ge.value} key={ge.value}>{ge.label}</option>)}</select>}<label className={`cand-toggle${y ? " cand-toggle--on" : ""}${(c == null ? undefined : c.pending_count) > 0 ? " cand-toggle--has-pending" : ""}`} title="Show only candidates with a pending balance"><input type="checkbox" checked={y} onChange={ge => k(ge.target.checked)} /><span>Pending only</span>{(c == null ? undefined : c.pending_count) > 0 && <span className="cand-toggle-badge">{c.pending_count}</span>}</label><div className="cand-toolbar-spacer" /><span className="cand-toolbar-count">{$e && <span className="cand-toolbar-scope">{$e} ·</span>}{T !== "all" && <span className="cand-toolbar-scope cand-toolbar-scope--ref">{T} ·</span>}{De === ye ? `${ye} candidate${ye === 1 ? "" : "s"}` : `${De} of ${ye}`}</span></div>{x && <div className="cand-error">{x}</div>}<div className="cand-table-wrap"><table className="cand-table"><thead><tr><th>Name</th><th>Technology</th><th>Stage</th><th>Payment</th><th>Date</th><th>Phone</th><th>Service</th>{a && <th>Reference</th>}<th aria-label="Actions" /></tr></thead><tbody>{f && i.length === 0 ? <tr><td colSpan={a ? 9 : 8} className="cand-table-empty">Loading…</td></tr> : i.length === 0 ? <tr><td colSpan={a ? 9 : 8} className="cand-table-empty">No candidates match these filters. <button type="button" className="cand-link" onClick={q}>Add one</button>.</td></tr> : i.map(ge => {
            const Ge = fR(ge.stage);
            return <tr className={`cand-row${ge.needs_followup ? " cand-row--pending" : ""}`} onClick={() => I(ge)} key={ge.id}><td className="cand-cell-name"><span className="cand-name">{ge.name}</span>{ge.consultancy && <span className="cand-channel-tag cand-channel-tag--consultancy" title="Came via a consultancy partner — ₹15,000 baseline">Consultancy</span>}{ge.service_type === "round_wise" && <span className="cand-channel-tag cand-channel-tag--roundwise" title="Round-wise interview support">Round-wise{ge.interview_scope === "non_domestic" ? " · intl" : ""}</span>}{(!ge.service_type || ge.service_type === "profile_service") && !ge.consultancy && <span className="cand-channel-tag cand-channel-tag--profile" title="Profile service — ₹20,000 baseline">Profile</span>}{ge.notes && <span className="cand-cell-note" title={ge.notes}>· {ge.notes.slice(0, 30)}{ge.notes.length > 30 ? "…" : ""}</span>}{ge.follow_up && <span className="cand-cell-followup" title={ge.follow_up}><span aria-hidden={true}>⟳</span> {ge.follow_up.slice(0, 60)}{ge.follow_up.length > 60 ? "…" : ""}</span>}</td><td>{ge.technology || "—"}</td><td><span className={`cand-badge ${Ge.cls}`}>{Ge.label}</span></td><td><_Component27 row={ge} onViewProofs={Z} /></td><td className="cand-cell-mono">{pR(ge.date)}</td><td className="cand-cell-mono cand-cell-phone" onClick={Ze => Ze.stopPropagation()}><_Component23 phone={ge.phone} /></td><td>{ge.service_type === "round_wise" ? <span className="cand-channel-tag cand-channel-tag--roundwise" title={ge.slot_confirmed ? "Round-wise · slot confirmed" : "Round-wise · slot pending"}>Slot{ge.slot_confirmed ? " ✓" : ""}</span> : <span className="cand-channel-tag cand-channel-tag--profile" title="Full profile placement">Profile</span>}</td>{a && <td className="cand-cell-ref">{ge.reference || "—"}</td>}<td className="cand-cell-actions" onClick={Ze => Ze.stopPropagation()}><button type="button" className="cand-btn cand-btn--ghost cand-btn--xs" onClick={() => I(ge)} title="Edit">✎</button>{a && <button type="button" className="cand-btn cand-btn--ghost cand-btn--xs cand-btn--danger-ghost" onClick={() => Pe(ge)} title="Delete">🗑</button>}</td></tr>;
          })}</tbody></table></div>{L && <X8 initial={C} handlerReference={n ? t : null} lockReference={n} isAdmin={a} onClose={Oe} onSave={Re} />}{ce && <_Component28 stats={c} scopeLabel={$e} onClose={() => ee(false)} onManage={a ? ue : undefined} />}{J && a && <_Component29 handlerNames={((c == null ? undefined : c.top_performers) || []).map(ge => ge.name).filter(Boolean)} ownedSummary={{
      owed: (c == null ? undefined : c.handler_auto_earnings_total) ?? (c == null ? undefined : c.handler_earnings_total) ?? 0,
      paid: (c == null ? undefined : c.handler_paid_out_total) ?? (c == null ? undefined : c.handler_deductions_total) ?? 0,
      net: (c == null ? undefined : c.net_handler_payout) ?? 0
    }} onClose={() => G(false)} onChanged={fe} />}{P && a && <_Component30 handler={P} onClose={() => j(null)} onChanged={fe} />}{B && <_Component31 candidate={B} onClose={() => Z(null)} onEdit={ge => I(ge)} />}<CandidatesActiveRoster open={ro} onClose={() => setRo(false)} reference={T} /><_Component32 open={!!W} title={W == null ? undefined : W.title} message={W == null ? undefined : W.message} onVerified={W == null ? undefined : W.onVerified} onCancel={H} /></div>;
}
