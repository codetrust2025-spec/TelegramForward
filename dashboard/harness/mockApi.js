/**
 * Deterministic API mock for the responsive harness.
 *
 * Every panel is measured against the same four shapes so a layout is proven
 * against an empty screen, a normal one, one with text long enough to wrap or
 * clip, and one with enough rows to exercise scrolling.
 */
const LONG =
  "Venkata Satyanarayana Raju Suryadevara Kalyanasundaram Chandrasekhar";
const LONG_TECH = "Senior Full Stack Engineer — React / Node / AWS / Kubernetes";

function candidate(i, mode) {
  const long = mode === "long";
  return {
    id: `cand-${i}`,
    name: long ? `${LONG} ${i}` : `Candidate ${i}`,
    phone: `98${String(100000 + i).slice(0, 8)}`,
    email: long ? `${LONG.replace(/\s+/g, ".").toLowerCase()}@example.com` : `c${i}@example.com`,
    technology: long ? LONG_TECH : "React JS",
    reference: long ? `${LONG} (referrer)` : ["Thrilok", "Pavan Kalyan", "Venugopal"][i % 3],
    stage: ["in_progress", "completed", "dropped", "fail"][i % 4],
    payment: 6000 + i * 137,
    expected_payment: 20000,
    balance_due: Math.max(0, 20000 - (6000 + i * 137)),
    payment_status: i % 3 === 0 ? "paid" : "partial",
    service_type: i % 5 === 0 ? "round_wise" : "profile_service",
    date: `2026-07-${String((i % 28) + 1).padStart(2, "0")}`,
    logged_date: `2026-07-${String((i % 28) + 1).padStart(2, "0")}`,
    notes: long ? LONG.repeat(3) : "",
    follow_up: long ? `${LONG} needs a call back about the offer letter` : "",
    handler_commission: 3000 + i * 60,
    closure_date: i % 4 === 1 ? "2026-07-15" : "",
    interview_round: ["L1", "L2", "HR"][i % 3],
    slot_confirmed: i % 2 === 0,
  };
}

function performers(mode) {
  const base = [
    { name: "Thrilok", count: 4, completed: 0, revenue_total: 54000, commission_total: 27000,
      salary_total: 15000, auto_earnings_total: 42000, paid_out_total: 42000, recoveries_total: 0,
      prior_balance: 5000, prior_owed: 50000, prior_paid: 45000, prior_months: ["2026-06"],
      prior_complimentary: 5000, prior_complimentary_count: 1, net_payable: 5000 },
    { name: "Venugopal", count: 3, completed: 0, revenue_total: 42000, commission_total: 20000,
      salary_total: 0, auto_earnings_total: 20000, paid_out_total: 0, recoveries_total: 0,
      prior_balance: 0, net_payable: 20000 },
    { name: "Pavan Kalyan", count: 2, completed: 0, revenue_total: 10000, commission_total: 5000,
      salary_total: 0, auto_earnings_total: 5000, paid_out_total: 6000, recoveries_total: 0,
      prior_balance: 12000, prior_months: ["2026-06"], net_payable: 11000 },
  ];
  if (mode === "empty") return [];
  if (mode === "long")
    return base.map((p, i) => ({ ...p, name: `${LONG} ${i}` }));
  if (mode === "bulk")
    return Array.from({ length: 40 }, (_, i) => ({ ...base[i % 3], name: `Handler ${i}` }));
  return base;
}

export function installMockApi(mode = "normal") {
  const count = mode === "empty" ? 0 : mode === "bulk" ? 120 : mode === "long" ? 6 : 12;
  const candidates = Array.from({ length: count }, (_, i) => candidate(i, mode));

  const routes = [
    [/\/auth\/status/, { status: "ok", authenticated: true, role: "admin", username: "harness", reference: "Thrilok" }],
    [/\/candidates\b/, { status: "ok", candidates, count: candidates.length }],
    [/\/stats/, {
      status: "ok", total: candidates.length, revenue: 106000, by_stage: {},
      top_performers: performers(mode),
      month_options: [{ value: "2026-07", label: "Jul 2026 · this month" }, { value: "all", label: "All months" }],
    }],
    [/\/ai\/ocr-policy\/audit/, { status: "ok", entries: [] }],
    [/\/ai\/ocr-policy/, { enabled: false, mode: "ai", source: "admin", updated_by: "admin" }],
    [/\/ai\/smart-reply\/config/, { status: "ok", config: { enabled: false, mode: "manual", model: "gpt-4o-mini" }, health: { api_key_present: true, available: false } }],
    [/\/ai\/smart-reply\/(assessment|evals)/, { status: "ok" }],
    [/\/accounts/, { status: "ok", accounts: [], slots: [] }],
    [/\/logs/, { status: "ok", logs: [], entries: [] }],
    [/\/public\/slots\/booked/, { status: "ok", slots: [] }],
    [/\/handler(-|_)?(expenses|salaries)/, { status: "ok", expenses: [], salaries: {} }],
    [/\/referrers/, { status: "ok", referrers: [{ id: "r1", name: "Thrilok" }] }],
  ];

  const respond = (url) => {
    for (const [re, body] of routes) if (re.test(url)) return body;
    return { status: "ok" };
  };

  window.fetch = (input, init) => {
    const url = typeof input === "string" ? input : (input && input.url) || "";
    const body = respond(String(url));
    return Promise.resolve({
      ok: true, status: 200, url: String(url),
      headers: { get: () => "application/json" },
      json: () => Promise.resolve(body),
      text: () => Promise.resolve(JSON.stringify(body)),
      blob: () => Promise.resolve(new Blob([JSON.stringify(body)])),
    });
  };
  window.EventSource = class { constructor() { this.close = () => {}; this.addEventListener = () => {}; } };
  if (!window.matchMedia) window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} });
}
