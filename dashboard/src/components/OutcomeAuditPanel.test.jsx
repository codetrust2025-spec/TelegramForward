import React from "react";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../context/ConfirmContext.jsx", () => ({
  useConfirm: () => ({ confirm: vi.fn(async () => true) }),
}));

import { OutcomeAuditPanel } from "./OutcomeAuditPanel.jsx";

const SUMMARY = {
  total_connected_mailboxes: 2,
  mailboxes_scanned: 2,
  mailboxes_failed: 0,
  candidates_with_interview_invites: 1,
  candidates_verified_offer_letters: 1,
  candidates_manual_review: 1,
  candidates_status_mismatch: 1,
  emails_missed_or_misclassified: 3,
  sync_or_queue_failures: 1,
  latest_run: {
    started_at: "2026-08-05T09:00:00Z",
    status: "COMPLETED",
    mode: "REPORT_ONLY",
    messages_examined: 412,
    incremental: false,
  },
};

const OFFER_CANDIDATE = {
  canonical_candidate_id: "9000031215",
  candidate_name: "Abilash Perla",
  email_address: "abiperla.536@gmail.com",
  monitoring_status: "MONITORING_ACTIVE",
  scan_status: "SCANNED",
  strongest_outcome: "VERIFIED_OFFER_LETTER",
  strongest_confidence: 92,
  strongest_authenticity: "PASS",
  system_status: "Interview Confirmed",
  status_mismatch: true,
  mismatch_detail: "Mail evidence supports 'Offer Received'; TeleAutomation shows 'Interview Confirmed'.",
  companies: ["Acme Corp"],
  conflicting_evidence: false,
  suspicious_evidence: false,
  last_successful_sync_at: "2026-08-05T08:55:00Z",
  recommended_action: "Review and, if correct, approve the status update to 'Offer Received'.",
};

const REVIEW_CANDIDATE = {
  canonical_candidate_id: "6301596228",
  candidate_name: "Shailaja",
  email_address: "sailajachennu761@gmail.com",
  monitoring_status: "MONITORING_ACTIVE",
  scan_status: "SCANNED",
  strongest_outcome: "MANUAL_REVIEW_REQUIRED",
  strongest_confidence: 50,
  strongest_authenticity: "SUSPICIOUS",
  system_status: null,
  status_mismatch: false,
  companies: [],
  conflicting_evidence: true,
  suspicious_evidence: true,
  last_successful_sync_at: "2026-08-05T08:50:00Z",
  recommended_action: "Human review: conflicting outcomes for the same company.",
};

const FINDINGS = [
  {
    id: "finding-1",
    outcome: "VERIFIED_OFFER_LETTER",
    confidence: 92,
    received_at: "2026-07-20T06:00:00Z",
    subject: "Your offer letter",
    sender_email: "hr@acme-corp.example",
    sender_name: "Acme HR",
    company_name: "Acme Corp",
    rationale: "Offer document Offer_Letter_Acme.pdf contains genuine offer details.",
    evidence: [{ source: "ATTACHMENT", meaning: "OFFER_LETTER_CONTENT", text: "annual CTC is INR 24,00,000" }],
    attachment_evidence: [
      { filename: "Offer_Letter_Acme.pdf", extraction_status: "COMPLETED", has_text: true },
    ],
    authenticity: "PASS",
    authenticity_detail: { concerns: [], notes: [] },
    pipeline_outcome: "INTERVIEW_INVITE",
    pipeline_agreement: "AUDIT_STRONGER",
  },
  {
    id: "finding-2",
    outcome: "NOT_RELEVANT",
    confidence: 60,
    received_at: "2026-07-01T06:00:00Z",
    subject: "Job alert",
    sender_email: "alerts@naukri.com",
    rationale: "Job-portal or transactional mail.",
    evidence: [],
    attachment_evidence: [],
    authenticity: "PARTIAL",
    authenticity_detail: { concerns: [], notes: [] },
    pipeline_outcome: null,
    pipeline_agreement: "NO_PIPELINE_RESULT",
  },
];

const GAPS = [
  {
    id: "gap-1",
    gap_type: "MISSING_EVENT",
    severity: "HIGH",
    canonical_candidate_id: "9000031215",
    candidate_name: "Abilash Perla",
    email_address: "abiperla.536@gmail.com",
    detail: "The audit reads this mail as VERIFIED_OFFER_LETTER but no recruitment event exists.",
    audit_outcome: "VERIFIED_OFFER_LETTER",
    pipeline_outcome: null,
  },
];

let calls;

function jsonResponse(body) {
  return Promise.resolve({ ok: true, json: () => Promise.resolve(body) });
}

function mockFetch(overrides = {}) {
  calls = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url, options) => {
      const path = String(url);
      calls.push({ path, options });
      if (path.includes("/mail-outcome-audit/summary"))
        return jsonResponse({ status: "ok", summary: overrides.summary ?? SUMMARY });
      if (path.includes("/mail-outcome-audit/candidates/"))
        return jsonResponse({
          status: "ok",
          candidate: OFFER_CANDIDATE,
          findings: FINDINGS,
          gaps: GAPS,
          approvals: [],
        });
      if (path.includes("/mail-outcome-audit/candidates"))
        return jsonResponse({
          status: "ok",
          candidates: overrides.candidates ?? [OFFER_CANDIDATE, REVIEW_CANDIDATE],
        });
      if (path.includes("/mail-outcome-audit/gaps"))
        return jsonResponse({ status: "ok", gaps: GAPS });
      if (path.includes("/mail-outcome-audit/run"))
        return jsonResponse({
          status: "ok",
          run: {
            mailboxes_total: 2, mailboxes_scanned: 2, mailboxes_failed: 0,
            messages_examined: 412, gaps_written: 1,
          },
        });
      if (path.includes("/approve"))
        return jsonResponse({
          status: "ok",
          approval: { status: "Offer Received", candidate_id: "9000031215", applied: true },
        });
      return jsonResponse({ status: "ok" });
    }),
  );
}

beforeEach(() => mockFetch());
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

async function renderPanel() {
  const view = render(<OutcomeAuditPanel />);
  await screen.findByText("Abilash Perla");
  return view;
}

describe("Outcome audit report", () => {
  it("states plainly that the audit is read-only", async () => {
    await renderPanel();
    expect(
      screen.getByText(/no email is sent, deleted, labelled or modified/i),
    ).toBeTruthy();
  });

  it("shows the system-wide summary tiles", async () => {
    await renderPanel();
    expect(screen.getByText("Connected mailboxes")).toBeTruthy();
    expect(screen.getByText("Verified offer letters")).toBeTruthy();
    expect(screen.getByText("Mail missed / misclassified")).toBeTruthy();
    expect(screen.getByText(/report only/i)).toBeTruthy();
  });

  it("lists each audited candidate with their strongest outcome", async () => {
    await renderPanel();
    const row = screen.getByText("Abilash Perla").closest("tr");
    expect(within(row).getByText("Verified offer letter")).toBeTruthy();
    expect(within(row).getByText("92%")).toBeTruthy();
    expect(within(row).getByText("Mismatch")).toBeTruthy();
  });

  it("marks conflicting and suspicious evidence", async () => {
    await renderPanel();
    const row = screen.getByText("Shailaja").closest("tr");
    expect(within(row).getByText("Conflicting evidence")).toBeTruthy();
    expect(within(row).getByText("Authenticity concern")).toBeTruthy();
  });

  it("sends every filter to the API", async () => {
    await renderPanel();
    fireEvent.change(screen.getByLabelText("Filter by outcome"), {
      target: { value: "VERIFIED_OFFER_LETTER" },
    });
    await waitFor(() =>
      expect(
        calls.some((c) => c.path.includes("outcome=VERIFIED_OFFER_LETTER")),
      ).toBe(true),
    );

    fireEvent.click(screen.getByLabelText(/manual review only/i, { selector: "input" }));
    await waitFor(() =>
      expect(calls.some((c) => c.path.includes("manual_review=1"))).toBe(true),
    );
  });

  it("opens the evidence drawer with the audit's reasoning", async () => {
    await renderPanel();
    const row = screen.getByText("Abilash Perla").closest("tr");
    fireEvent.click(within(row).getByText("Evidence"));

    await screen.findByText("Your offer letter");
    expect(
      screen.getByText(/contains genuine offer details/i),
    ).toBeTruthy();
    expect(screen.getByText(/annual CTC is INR 24,00,000/)).toBeTruthy();
    // The filename appears in both the rationale and the attachment line.
    expect(screen.getAllByText(/Offer_Letter_Acme\.pdf/).length).toBeGreaterThan(0);
    expect(screen.getByText(/text read/)).toBeTruthy();
  });

  it("hides irrelevant mail from the evidence list", async () => {
    await renderPanel();
    fireEvent.click(
      within(screen.getByText("Abilash Perla").closest("tr")).getByText("Evidence"),
    );
    await screen.findByText("Your offer letter");
    expect(screen.queryByText("Job alert")).toBeNull();
  });

  it("requires an explicit approval to change a candidate status", async () => {
    await renderPanel();
    fireEvent.click(
      within(screen.getByText("Abilash Perla").closest("tr")).getByText("Evidence"),
    );
    const approve = await screen.findByText("Approve status update");

    // Nothing has been applied merely by viewing the report.
    expect(calls.some((c) => c.path.includes("/approve"))).toBe(false);

    fireEvent.click(approve);
    await waitFor(() =>
      expect(
        calls.some(
          (c) => c.path.includes("/findings/finding-1/approve") && c.options?.method === "POST",
        ),
      ).toBe(true),
    );
    const call = calls.find((c) => c.path.includes("/approve"));
    expect(JSON.parse(call.options.body)).toEqual({ decision: "APPROVED" });
  });

  it("runs the audit in report-only mode", async () => {
    await renderPanel();
    fireEvent.click(screen.getByText("Run full audit"));
    await waitFor(() =>
      expect(calls.some((c) => c.path.includes("/mail-outcome-audit/run"))).toBe(true),
    );
    const call = calls.find((c) => c.path.includes("/run"));
    expect(JSON.parse(call.options.body)).toEqual({ incremental: false });
    // The run summary notice, distinct from the "last run" line above it.
    expect(
      await screen.findByText(/Audit complete — 2\/2 mailboxes scanned, 412 messages examined/),
    ).toBeTruthy();
  });

  it("shows pipeline gaps the audit found", async () => {
    await renderPanel();
    fireEvent.click(screen.getByText(/Pipeline gaps/));
    expect(await screen.findByText("Missing event")).toBeTruthy();
    expect(screen.getByText(/no recruitment event exists/)).toBeTruthy();
  });

  it("explains an empty report instead of showing a blank table", async () => {
    mockFetch({ candidates: [] });
    render(<OutcomeAuditPanel />);
    expect(
      await screen.findByText(/No audited mailboxes match these filters/i),
    ).toBeTruthy();
  });
});
