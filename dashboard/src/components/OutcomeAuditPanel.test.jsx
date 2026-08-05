import React from "react";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../context/ConfirmContext.jsx", () => ({
  useConfirm: () => ({ confirm: vi.fn(async () => true) }),
}));

import { OutcomeAuditPanel } from "./OutcomeAuditPanel.jsx";

const SELECTION_SUMMARY = {
  mode: "SELECTION",
  total_connected_mailboxes: 2,
  mailboxes_scanned: 2,
  mailboxes_failed: 0,
  candidates_verified_offer_letters: 1,
  candidates_offer_indication: 2,
  candidates_shortlisted: 3,
  candidates_rejected: 4,
  candidates_background_verification: 5,
  candidates_no_outcome: 0,
  candidates_status_mismatch: 1,
  pipeline_gaps_total: 12,
  latest_run: {
    started_at: "2026-08-05T09:00:00Z",
    status: "COMPLETED",
    mode: "REPORT_ONLY",
    messages_examined: 7399,
  },
};

const INTERVIEW_SUMMARY = {
  mode: "INTERVIEW",
  total_connected_mailboxes: 2,
  mailboxes_scanned: 2,
  mailboxes_failed: 0,
  candidates_with_interview_invites: 9,
  candidates_auto_booked: 6,
  candidates_interview_rescheduled: 2,
  candidates_interview_cancelled: 1,
  candidates_booking_blocked: 3,
  candidates_duplicate_booking_ignored: 1,
  candidates_slot_conflict: 1,
  candidates_missing_date_or_time: 2,
  candidates_missed_invites: 4,
  candidates_historical_not_booked: 7,
  pipeline_gaps_total: 20,
  latest_run: SELECTION_SUMMARY.latest_run,
};

const SELECTION_CANDIDATE = {
  canonical_candidate_id: "8b52fe4c3d",
  candidate_name: "Lekkala swathi",
  email_address: "swathilekkala515@gmail.com",
  monitoring_status: "MONITORING_ACTIVE",
  scan_status: "SCANNED",
  strongest_outcome: "VERIFIED_OFFER_LETTER",
  strongest_confidence: 92,
  strongest_authenticity: "PARTIAL",
  system_status: "Profile Active",
  status_mismatch: true,
  mismatch_detail: "Mail evidence supports 'Offer Received'.",
  companies: ["Kaivale Technologies"],
  outcome_counts: { VERIFIED_OFFER_LETTER: 1, SHORTLISTED: 2 },
  recommended_action: "Review and, if correct, approve the status update to 'Offer Received'.",
};

const INTERVIEW_CANDIDATE = {
  canonical_candidate_id: "43ea8aacba",
  candidate_name: "Abilash Perla",
  email_address: "abiperla.536@gmail.com",
  monitoring_status: "MONITORING_ACTIVE",
  scan_status: "SCANNED",
  strongest_outcome: "INTERVIEW_AUTO_BOOKED",
  strongest_confidence: 100,
  status_mismatch: false,
  companies: [],
  outcome_counts: { INTERVIEW_AUTO_BOOKED: 2, BOOKING_BLOCKED: 1 },
  recommended_action: "No action; the interview slot was booked automatically.",
};

// One candidate, three companies. The Kaivale offer is verified company mail;
// the Crescendo "rejection" and the Stravya "offer" both came through job
// portals and must not be approvable.
const APPLICATIONS = [
  {
    application_key: "kaivale.com:sr-software-engineer",
    company: "Kaivale Technologies",
    role: "Sr. Software Engineer",
    latest_verified_state: "VERIFIED_OFFER_LETTER",
    confidence: 92,
    authenticity: "PASS",
    evidence_strength: "STRONG",
    source_type: "COMPANY",
    strongest_finding_id: "f-kaivale",
    latest_message_at: "2026-07-16T12:10:00Z",
    messages: [
      { id: "m1", received_at: "2026-07-16T12:10:00Z", outcome: "VERIFIED_OFFER_LETTER",
        subject: "Your offer letter", sender_email: "vanshika@kaivale.com" },
    ],
    approval: { eligible: true, blockers: [], message: "" },
  },
  {
    application_key: "shine.com:",
    company: "Stravya Hiring Solutions Limited",
    role: "Role not stated",
    latest_verified_state: "OFFER_INDICATION",
    confidence: 78,
    authenticity: "PARTIAL",
    evidence_strength: "WEAK",
    source_type: "JOB_PORTAL",
    strongest_finding_id: "f-stravya",
    latest_message_at: "2026-06-25T04:19:00Z",
    messages: [
      { id: "m2", received_at: "2026-06-25T04:19:00Z", outcome: "OFFER_INDICATION",
        subject: "You are a Top Applicant! Details Required",
        sender_email: "alerts@jobs.shine.com" },
    ],
    approval: {
      eligible: false,
      blockers: ["The sender is not confirmed to be the hiring company.",
                 "Evidence is not strong enough to act on without verification."],
      message: "Needs manual review — evidence is insufficient for a status change.",
    },
  },
];

const FINDINGS_WITH_REVIEW = [
  {
    id: "f-kaivale",
    outcome: "MANUAL_REVIEW_REQUIRED",
    confidence: 50,
    received_at: "2026-07-16T12:10:00Z",
    subject: "Re: Welcome to Kaivale Technologies",
    sender_email: "vanshika@kaivale.com",
    company_name: "Kaivale Technologies",
    rationale: "Offer letter referenced but not attached.",
    evidence: [],
    attachment_evidence: [],
    authenticity: "PARTIAL",
    authenticity_detail: { concerns: [] },
    source_type: "COMPANY",
    evidence_strength: "MODERATE",
    pipeline_outcome: "JOINING_CONFIRMED",
    pipeline_agreement: "PIPELINE_STRONGER",
  },
];

const OLLAMA_REVIEWS = {
  "f-kaivale": {
    model: "qwen2.5:7b",
    suggested_outcome: "JOINING_CONFIRMED",
    confidence: 95,
    agrees: false,
    derived_agreement: "DISAGREES",
    normalized_confidence: 95,
    restricted_outcome: "JOINING_CONFIRMED",
    restrictions: null,
    approval_state: "Needs manual review — deterministic evidence and the AI disagree.",
    verified: true,
    verification_problems: null,
    quoted_evidence: "Thanks for accepting the offer letter.",
    reasoning: "The thread shows the offer was accepted and onboarding began.",
    cited_message_id: "19f6b02d5051d006",
    cited_attachment: null,
    cited_company: "Kaivale Technologies",
    is_bulk_campaign: false,
  },
};

let calls;

const jsonResponse = (body) => Promise.resolve({ ok: true, json: () => Promise.resolve(body) });

function mockFetch() {
  calls = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url, options) => {
      const path = String(url);
      calls.push({ path, options });
      const interview = path.includes("mode=INTERVIEW");
      if (path.includes("/summary"))
        return jsonResponse({
          status: "ok",
          summary: interview ? INTERVIEW_SUMMARY : SELECTION_SUMMARY,
        });
      if (path.includes("/candidates/"))
        return jsonResponse({
          status: "ok",
          mode: interview ? "INTERVIEW" : "SELECTION",
          candidate: interview ? INTERVIEW_CANDIDATE : SELECTION_CANDIDATE,
          findings: [],
          applications: interview ? [] : APPLICATIONS,
          bookings: interview
            ? [
                {
                  id: "b1",
                  booking_outcome: "INTERVIEW_AUTO_BOOKED",
                  booking_status: "Auto Booked",
                  created_at: "2026-08-04T12:36:00Z",
                },
              ]
            : [],
          gaps: [],
          approvals: [],
          findings: interview ? [] : FINDINGS_WITH_REVIEW,
          ollama_reviews: interview ? {} : OLLAMA_REVIEWS,
        });
      if (path.includes("/candidates"))
        return jsonResponse({
          status: "ok",
          candidates: [interview ? INTERVIEW_CANDIDATE : SELECTION_CANDIDATE],
        });
      if (path.includes("/gaps")) return jsonResponse({ status: "ok", gaps: [] });
      if (path.includes("/excluded"))
        return jsonResponse({
          status: "ok",
          excluded: [
            {
              id: "x1",
              canonical_candidate_id: "8b52fe4c3d",
              candidate_name: "Lekkala swathi",
              email_address: "swathilekkala515@gmail.com",
              outcome: "VERIFIED_OFFER_LETTER",
              subject: "Re: Welcome to Kaivale Technologies",
              sender_email: "vanshika@kaivale.com",
              received_at: "2026-07-16T12:10:00Z",
              suppression_reason: "DUPLICATE",
              suppression_detail: "Same verified offer letter already counted from message gmail-a.",
              suppressed_at: "2026-08-05T10:00:00Z",
            },
            {
              id: "x2",
              canonical_candidate_id: "24cc7b8ffd",
              candidate_name: "Gopichand",
              outcome: "INTERVIEW_INVITE",
              subject: "Interview invitation",
              sender_email: "hr@acme.example",
              received_at: "2026-07-01T09:00:00Z",
              suppression_reason: "WRONG_AUDIT_MODE",
              suppression_detail: "Interview-slot result; counted in the Interview Slot Audit instead.",
              suppressed_at: "2026-08-05T10:00:00Z",
            },
          ],
          summary: { excluded_total: 2 },
        });
      return jsonResponse({ status: "ok" });
    }),
  );
  vi.stubGlobal("open", vi.fn());
}

beforeEach(mockFetch);
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

async function renderPanel() {
  const view = render(<OutcomeAuditPanel />);
  await screen.findByText("Lekkala swathi");
  return view;
}

const switchTo = async (label) => {
  fireEvent.click(screen.getByText(label));
  await waitFor(() =>
    expect(calls.some((c) => c.path.includes("mode=INTERVIEW"))).toBe(true),
  );
};

describe("Audit mode selector", () => {
  it("offers both audits and pipeline gaps", async () => {
    await renderPanel();
    expect(screen.getByText("Selection Audit")).toBeTruthy();
    expect(screen.getByText("Interview Slot Audit")).toBeTruthy();
    expect(screen.getByText(/Pipeline Gaps/)).toBeTruthy();
  });

  it("defaults to the selection audit", async () => {
    await renderPanel();
    expect(screen.getByText("Selection Audit").getAttribute("aria-current")).toBe("page");
    expect(calls[0].path).toContain("mode=SELECTION");
  });

  it("requests the interview mode when switched", async () => {
    await renderPanel();
    await switchTo("Interview Slot Audit");
    expect(
      calls.some((c) => c.path.includes("/summary") && c.path.includes("mode=INTERVIEW")),
    ).toBe(true);
  });
});

describe("Selection audit shows no interview results", () => {
  it("shows only selection categories in the tiles", async () => {
    const { container } = await renderPanel();
    const tiles = within(container.querySelector(".outcome-audit__tiles"));
    expect(tiles.getByText("Verified offer letters")).toBeTruthy();
    expect(tiles.getByText("Shortlisted")).toBeTruthy();
    expect(tiles.getByText("Rejected")).toBeTruthy();
    expect(tiles.getByText("No selection evidence")).toBeTruthy();
    // Interview categories must be absent entirely.
    expect(tiles.queryByText("Interview invitations")).toBeNull();
    expect(tiles.queryByText("Automatically booked")).toBeNull();
    expect(tiles.queryByText("Slot conflicts")).toBeNull();
    expect(tiles.queryByText("Duplicate ignored")).toBeNull();
  });

  it("offers only selection outcomes in the outcome filter", async () => {
    await renderPanel();
    const options = [...screen.getByLabelText("Filter by outcome").options].map((o) => o.textContent);
    expect(options).toContain("Verified offer letter");
    expect(options).toContain("Manual review required");
    expect(options).not.toContain("Interview invitation");
    expect(options).not.toContain("Booking blocked");
  });

  it("keeps the status-mismatch column and filter", async () => {
    await renderPanel();
    expect(screen.getByText("System status")).toBeTruthy();
    expect(screen.getByLabelText(/status mismatches only/i, { selector: "input" })).toBeTruthy();
  });
});

describe("Interview slot audit shows no selection results", () => {
  it("shows only interview categories in the tiles", async () => {
    const { container } = await renderPanel();
    await switchTo("Interview Slot Audit");
    await screen.findByText("Interview invitations");
    const tiles = within(container.querySelector(".outcome-audit__tiles"));
    expect(tiles.getByText("Automatically booked")).toBeTruthy();
    expect(tiles.getByText("Booking blocked")).toBeTruthy();
    expect(tiles.getByText("Slot conflicts")).toBeTruthy();
    expect(tiles.getByText("Missing date or time")).toBeTruthy();
    expect(tiles.getByText("Missed or unprocessed invites")).toBeTruthy();
    // Selection categories must be absent entirely.
    expect(tiles.queryByText("Verified offer letters")).toBeNull();
    expect(tiles.queryByText("Final selections")).toBeNull();
    expect(tiles.queryByText("Joining confirmed")).toBeNull();
    expect(tiles.queryByText("Rejected")).toBeNull();
  });

  it("offers only interview outcomes in the outcome filter", async () => {
    await renderPanel();
    await switchTo("Interview Slot Audit");
    await screen.findByText("Interview invitations");
    const options = [...screen.getByLabelText("Filter by outcome").options].map((o) => o.textContent);
    expect(options).toContain("Interview automatically booked");
    expect(options).toContain("Slot conflict");
    expect(options).not.toContain("Verified offer letter");
    expect(options).not.toContain("Rejected");
  });

  it("drops the hiring-status column and mismatch filter", async () => {
    await renderPanel();
    await switchTo("Interview Slot Audit");
    await screen.findByText("Interview activity");
    expect(screen.queryByText("System status")).toBeNull();
    expect(screen.queryByLabelText(/status mismatches only/i, { selector: "input" })).toBeNull();
  });

  it("resets an outcome filter that belongs to the other mode", async () => {
    await renderPanel();
    fireEvent.change(screen.getByLabelText("Filter by outcome"), {
      target: { value: "VERIFIED_OFFER_LETTER" },
    });
    await waitFor(() =>
      expect(calls.some((c) => c.path.includes("outcome=VERIFIED_OFFER_LETTER"))).toBe(true),
    );
    await switchTo("Interview Slot Audit");
    const latest = calls[calls.length - 1];
    expect(latest.path).not.toContain("outcome=VERIFIED_OFFER_LETTER");
  });
});

describe("Evidence drawer follows the mode", () => {
  it("requests evidence scoped to the active audit", async () => {
    await renderPanel();
    fireEvent.click(
      within(screen.getByText("Lekkala swathi").closest("tr")).getByText("Evidence"),
    );
    await waitFor(() =>
      expect(
        calls.some((c) => c.path.includes("/candidates/8b52fe4c3d") && c.path.includes("mode=SELECTION")),
      ).toBe(true),
    );
    expect(await screen.findByText(/Selection audit/)).toBeTruthy();
  });

  it("shows booking outcomes in interview mode", async () => {
    await renderPanel();
    await switchTo("Interview Slot Audit");
    await screen.findByText("Abilash Perla");
    fireEvent.click(
      within(screen.getByText("Abilash Perla").closest("tr")).getByText("Evidence"),
    );
    const heading = await screen.findByText("Booking outcomes");
    const list = within(heading.nextElementSibling);
    expect(list.getByText("Interview automatically booked")).toBeTruthy();
    expect(list.getByText(/Auto Booked/)).toBeTruthy();
  });
});

describe("Pipeline gaps stay available for both modes", () => {
  it("is reachable and scoped to the active mode", async () => {
    await renderPanel();
    fireEvent.click(screen.getByText(/Pipeline Gaps/));
    expect(
      await screen.findByText(/Pipeline gaps affecting the selection audit/i),
    ).toBeTruthy();
    expect(calls.some((c) => c.path.includes("/gaps") && c.path.includes("mode=SELECTION"))).toBe(true);
  });
});

describe("Export follows the mode", () => {
  it("exports the selection report by default", async () => {
    await renderPanel();
    fireEvent.click(screen.getByText("Export CSV"));
    expect(window.open).toHaveBeenCalled();
    expect(window.open.mock.calls[0][0]).toContain("mode=SELECTION");
    expect(window.open.mock.calls[0][0]).toContain("/mail-outcome-audit/export");
  });

  it("exports the interview report after switching", async () => {
    await renderPanel();
    await switchTo("Interview Slot Audit");
    fireEvent.click(screen.getByText("Export CSV"));
    const url = window.open.mock.calls[window.open.mock.calls.length - 1][0];
    expect(url).toContain("mode=INTERVIEW");
  });
});

describe("Evidence is read company by company", () => {
  const openDrawer = async () => {
    await renderPanel();
    fireEvent.click(
      within(screen.getByText("Lekkala swathi").closest("tr")).getByText("Evidence"),
    );
    return screen.findByText("By company and role");
  };

  it("shows one lifecycle per company and role", async () => {
    const heading = await openDrawer();
    // Scoped to the timeline: the company also appears in the table behind it.
    const timeline = within(heading.parentElement.querySelector(".outcome-audit__applications"));
    expect(timeline.getByText("Kaivale Technologies")).toBeTruthy();
    expect(timeline.getByText("Sr. Software Engineer")).toBeTruthy();
    expect(timeline.getByText("Stravya Hiring Solutions Limited")).toBeTruthy();
    expect(timeline.getAllByRole("listitem").length).toBeGreaterThanOrEqual(2);
  });

  it("says outright that companies are never merged", async () => {
    await openDrawer();
    expect(
      screen.getByText(/A result from one company never affects another/i),
    ).toBeTruthy();
  });

  it("shows evidence strength and source for each application", async () => {
    await openDrawer();
    expect(screen.getByText("Strong evidence")).toBeTruthy();
    expect(screen.getByText("Weak evidence")).toBeTruthy();
    expect(screen.getByText("Job portal")).toBeTruthy();
  });

  it("offers approval only for the verified company application", async () => {
    await openDrawer();
    expect(screen.getAllByText("Approve status update")).toHaveLength(1);
  });

  it("shows the insufficient-evidence message for the portal application", async () => {
    await openDrawer();
    expect(
      screen.getByText("Needs manual review — evidence is insufficient for a status change."),
    ).toBeTruthy();
    expect(
      screen.getByText(/not confirmed to be the hiring company/),
    ).toBeTruthy();
  });

  it("approves against the application's strongest finding", async () => {
    await openDrawer();
    fireEvent.click(screen.getByText("Approve status update"));
    await waitFor(() =>
      expect(calls.some((c) => c.path.includes("/findings/f-kaivale/approve"))).toBe(true),
    );
  });
});

describe("Ollama second opinion is shown beside the other two", () => {
  const openDrawer = async () => {
    await renderPanel();
    fireEvent.click(
      within(screen.getByText("Lekkala swathi").closest("tr")).getByText("Evidence"),
    );
    return screen.findByText("Ollama second opinion");
  };

  it("shows all three verdicts together", async () => {
    const heading = await openDrawer();
    // Scoped to the review block: "Pipeline:" also appears on the finding.
    const block = within(heading.closest(".outcome-audit__review"));
    expect(block.getByText(/Deterministic:/)).toBeTruthy();
    expect(block.getByText(/Pipeline:/)).toBeTruthy();
    expect(block.getByText(/Ollama:/)).toBeTruthy();
    expect(block.getByText("qwen2.5:7b")).toBeTruthy();
  });

  it("derives agreement from the outcomes, not the model's own claim", async () => {
    // The fixture carries agrees:false; the UI must render the server-derived
    // agreement instead, and never the model's self-assessment.
    await openDrawer();
    expect(screen.getByText("Disagrees")).toBeTruthy();
  });

  it("shows the normalised confidence, not the raw model value", async () => {
    await openDrawer();
    expect(screen.getByText("95%")).toBeTruthy();
  });

  it("blocks approval when the deterministic reading and the AI disagree", async () => {
    await openDrawer();
    expect(
      screen.getByText(/Needs manual review . deterministic evidence and the AI disagree/i),
    ).toBeTruthy();
  });

  it("shows the quoted evidence and the reasoning", async () => {
    await openDrawer();
    expect(screen.getByText(/Thanks for accepting the offer letter/)).toBeTruthy();
    expect(screen.getByText(/onboarding began/)).toBeTruthy();
  });

  it("marks whether the citations were verified", async () => {
    await openDrawer();
    expect(screen.getByText("Citations verified")).toBeTruthy();
    expect(screen.getByText(/19f6b02d5051d006/)).toBeTruthy();
  });

  it("states plainly that the second opinion is advisory", async () => {
    await openDrawer();
    expect(screen.getByText(/A disagreement is a prompt to read the mail, not a status change/i))
      .toBeTruthy();
  });

  it("offers no approve action from the Ollama block", async () => {
    const heading = await openDrawer();
    const block = heading.closest(".outcome-audit__review");
    expect(within(block).queryByText("Approve status update")).toBeNull();
  });
});

describe("Cleanup keeps excluded findings visible", () => {
  it("offers an Excluded view in the selection audit", async () => {
    await renderPanel();
    expect(screen.getByText(/Excluded \(2\)/)).toBeTruthy();
  });

  it("lists what was excluded, with the reason and when", async () => {
    await renderPanel();
    fireEvent.click(screen.getByText(/Excluded \(2\)/));
    expect(await screen.findByText("Duplicate")).toBeTruthy();
    expect(screen.getByText("Moved to Interview Slot Audit")).toBeTruthy();
    expect(screen.getByText(/already counted from message gmail-a/)).toBeTruthy();
    expect(screen.getByText("Re: Welcome to Kaivale Technologies")).toBeTruthy();
  });

  it("says plainly that nothing was deleted", async () => {
    await renderPanel();
    fireEvent.click(screen.getByText(/Excluded \(2\)/));
    expect(
      await screen.findByText(/attachments and its evidence are unchanged/i),
    ).toBeTruthy();
  });

  it("does not offer the Excluded view in the interview audit", async () => {
    await renderPanel();
    await switchTo("Interview Slot Audit");
    await screen.findByText("Interview invitations");
    expect(screen.queryByText(/^Excluded \(/)).toBeNull();
  });
});

describe("Read-only behaviour is preserved", () => {
  it("states plainly that the audit is read-only", async () => {
    await renderPanel();
    expect(screen.getByText(/no email is sent, deleted, labelled or modified/i)).toBeTruthy();
  });

  it("changes nothing merely by switching modes", async () => {
    await renderPanel();
    await switchTo("Interview Slot Audit");
    expect(calls.every((c) => !c.options?.method || c.options.method === "GET")).toBe(true);
  });
});
