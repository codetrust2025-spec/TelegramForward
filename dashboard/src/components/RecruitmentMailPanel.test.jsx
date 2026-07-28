import React from "react";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  RecruitmentMailPanel,
  shouldShowInSelectionOfferReview,
} from "./RecruitmentMailPanel.jsx";
import { ConfirmProvider } from "../context/ConfirmContext.jsx";

const payloadFor = (url) => {
  if (url.includes("/ollama/status"))
    return {
      status: "ok",
      ollama: {
        status: "healthy",
        diagnostic_status: "AVAILABLE",
        last_checked_at: "2026-07-18T10:15:31Z",
      },
    };
  if (url.includes("/dashboard"))
    return {
      status: "ok",
      metrics: {
        selected: 1,
        offers_received: 0,
        offers_accepted: 0,
        joining_confirmed: 5,
        joined: 0,
        needs_review: 0,
      },
      charts: {},
      flags: [],
    };
  if (url.includes("/review")) return { status: "ok", events: [] };
  if (url.includes("/offer-verification")) return { status: "ok", cases: [] };
  if (url.includes("/mail-monitoring/notifications"))
    return {
      status: "ok",
      notifications: [
        {
          id: "notification-1",
          ai_recruitment_event_id: "event-1",
          candidate_id: "c1",
          candidate_name: "Test Candidate",
          classification: "interview_confirmed",
          email_subject: "Frontend interview invitation",
          interview_date: "2026-07-22",
          interview_time: "03:00 PM",
          interview_timezone: "Asia/Kolkata",
          ai_confidence: 0.8,
          booking_status: "Blocked",
        },
      ],
    };
  if (url.includes("/events/event-1"))
    return {
      status: "ok",
      event: {
        id: "event-1",
        subject: "Frontend interview invitation",
        primary_status: "INTERVIEW_CONFIRMED",
        review_status: "APPROVED",
        validation_status: "APPROVED",
        ai_status: "RETRY_PENDING",
        ai_model: "unavailable:ollama_request_timeout",
        summary:
          "Fallback evidence indicates interview confirmed. AI validation unavailable (OLLAMA_REQUEST_TIMEOUT).",
        evidence_summary:
          "Fallback evidence indicates interview confirmed. AI validation unavailable (OLLAMA_REQUEST_TIMEOUT).",
        structured_result: {
          evidence: [
            { meaning: "Interview confirmed", text: "Interview at 3 PM" },
          ],
        },
        received_email: {
          subject: "Frontend interview invitation",
          sender_name: "Recruiter",
          sender_email: "recruiter@example.com",
          recipient_email: "candidate@gmail.com",
          sent_at: "2026-07-21T08:00:00Z",
          body: "Your frontend interview is scheduled for tomorrow at 3 PM.",
        },
      },
    };
  if (url.includes("/candidates?"))
    return {
      status: "ok",
      candidates: [
        {
          id: "c1",
          name: "Test Candidate",
          phone: "9000000000",
          email: "test.candidate@gmail.com",
          stage: "in_progress",
          service_type: "profile_service",
        },
      ],
    };
  return { status: "ok" };
};

describe("RecruitmentMailPanel", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url) => ({
        ok: true,
        json: async () => payloadFor(String(url)),
      })),
    );
  });
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });
  it("renders the redesigned monitoring hub with separated journeys", async () => {
    render(
      <ConfirmProvider>
        <RecruitmentMailPanel />
      </ConfirmProvider>,
    );
    expect(
      screen.getByRole("heading", { name: "Mail & Interview Monitoring" }),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "Priority Mail Review" }),
      ).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: "Review Queue" })).toHaveClass(
      "active",
    );
    fireEvent.click(screen.getByRole("button", { name: "Overview" }));
    expect(
      screen.getByRole("heading", { name: "Selection & Offer flow" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Interview monitoring flow" }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Selection & Offers" }));
    expect(screen.getByText("Selected").closest("article")).toHaveTextContent(
      "1",
    );
    expect(screen.getByText("Offers").closest("article")).toHaveTextContent(
      "0 / 0",
    );
    expect(screen.getByText("Joining").closest("article")).toHaveTextContent(
      "5 / 0",
    );
    expect(
      screen.getByRole("button", { name: "Selection & Offers" }),
    ).toHaveClass("active");
  });
  it("keeps candidate data visible when Ollama diagnostics fail", async () => {
    fetch.mockImplementation(async (url) => {
      if (String(url).includes("/ollama/status")) {
        return {
          ok: false,
          json: async () => ({ detail: "diagnostics failed" }),
        };
      }
      return { ok: true, json: async () => payloadFor(String(url)) };
    });
    render(
      <ConfirmProvider>
        <RecruitmentMailPanel />
      </ConfirmProvider>,
    );
    expect(
      screen.queryByRole("button", { name: "Candidates" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Analytics" }),
    ).not.toBeInTheDocument();
    const globalCandidateFilter = await screen.findByLabelText(
      "Global candidate filter",
    );
    expect(globalCandidateFilter).toHaveValue("");
    fireEvent.change(globalCandidateFilter, { target: { value: "c1" } });
    fireEvent.click(screen.getByRole("button", { name: "Selection & Offers" }));
    expect(
      screen.getByRole("heading", { name: "Candidate history" }),
    ).toBeInTheDocument();
    expect(globalCandidateFilter).toHaveValue("c1");
    expect(
      screen.queryByRole("option", { name: "Select candidate" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Request failed")).not.toBeInTheDocument();
  });
  it("uses the header candidate selector as a global filter", async () => {
    render(
      <ConfirmProvider>
        <RecruitmentMailPanel />
      </ConfirmProvider>,
    );
    const globalCandidateFilter = await screen.findByLabelText(
      "Global candidate filter",
    );
    fireEvent.change(globalCandidateFilter, { target: { value: "c1" } });
    fireEvent.click(screen.getByRole("button", { name: "Selection & Offers" }));
    expect(
      screen.getByRole("heading", { name: "Candidate history" }),
    ).toBeInTheDocument();
    fireEvent.change(globalCandidateFilter, { target: { value: "" } });
    expect(
      screen.queryByRole("heading", { name: "Candidate history" }),
    ).not.toBeInTheDocument();
  });
  it("opens the complete source mail when an interview activity row is selected", async () => {
    render(
      <ConfirmProvider>
        <RecruitmentMailPanel />
      </ConfirmProvider>,
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Interview Monitoring" }),
    );
    const activity = await screen.findByLabelText(
      "Open source mail: Frontend interview invitation",
    );
    fireEvent.click(activity);
    expect(
      await screen.findByRole("heading", { name: "Detection Evidence" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Complete email" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Your frontend interview is scheduled for tomorrow at 3 PM.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText(/^Manually approved/)).toBeInTheDocument();
    expect(screen.getByText("Human approval")).toBeInTheDocument();
    expect(screen.getAllByText("Interview Confirmed").length).toBeGreaterThan(
      0,
    );
    expect(
      screen.getByText(
        "This record was manually approved from the complete source email. The earlier AI timeout is retained only in audit history.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/AI validation unavailable/),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("unavailable:ollama_request_timeout"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(
        /AI analysis is pending because the AI service was unavailable/,
      ),
    ).not.toBeInTheDocument();
  });
  it("opens Gmail connection inline from the main review screen", async () => {
    render(
      <ConfirmProvider>
        <RecruitmentMailPanel />
      </ConfirmProvider>,
    );
    const addButton = await screen.findByRole("button", {
      name: "+ Add candidate Gmail",
    });
    fireEvent.click(addButton);
    expect(
      screen.getByRole("heading", { name: "Connect a candidate Gmail" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Review Queue" })).toHaveClass(
      "active",
    );
    expect(
      screen.getByRole("button", { name: "Close Gmail form" }),
    ).toBeInTheDocument();
  });
  it("refreshes monitoring data without reloading the page", async () => {
    render(
      <ConfirmProvider>
        <RecruitmentMailPanel />
      </ConfirmProvider>,
    );
    expect(await screen.findByText("AI Available")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Refresh/ }));
    await waitFor(() =>
      expect(
        fetch.mock.calls.filter(([url]) =>
          String(url).includes("/candidate-mailboxes/overview"),
        ).length,
      ).toBeGreaterThanOrEqual(2),
    );
    expect(screen.getByText(/Last updated:/)).not.toHaveTextContent("Loading");
  });
  it("offers an add candidate Gmail form for candidates without a mailbox", async () => {
    render(
      <ConfirmProvider>
        <RecruitmentMailPanel />
      </ConfirmProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Mailboxes" }));
    const addButton = await screen.findByRole("button", {
      name: "+ Add candidate Gmail",
    });
    fireEvent.click(addButton);
    expect(
      screen.getByRole("heading", { name: "Connect a candidate Gmail" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("option", { name: /Test Candidate · 9000000000/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText(/^candidate@gmail\.com/),
    ).toHaveAttribute("type", "email");
    expect(
      screen.getByRole("button", { name: "Connect Gmail" }),
    ).toBeDisabled();
  });
  it("shows only in-progress profile candidates without a linked Gmail", async () => {
    fetch.mockImplementation(async (url) => {
      const path = String(url);
      if (path.includes("/candidates?"))
        return {
          ok: true,
          json: async () => ({
            status: "ok",
            candidates: [
              {
                id: "profile-pending",
                name: "Pending Profile",
                phone: "9111111111",
                email: "pending@example.com",
                stage: "in_progress",
                service_type: "profile_service",
              },
              {
                id: "round-wise",
                name: "Round Wise Candidate",
                stage: "in_progress",
                service_type: "round_wise",
              },
              {
                id: "completed-profile",
                name: "Completed Profile",
                stage: "completed",
                service_type: "profile_service",
              },
            ],
          }),
        };
      if (path.includes("/candidate-mailboxes/overview"))
        return {
          ok: true,
          json: async () => ({ status: "ok", mailboxes: [] }),
        };
      return { ok: true, json: async () => payloadFor(path) };
    });

    render(
      <ConfirmProvider>
        <RecruitmentMailPanel />
      </ConfirmProvider>,
    );
    const pendingTab = await screen.findByRole("tab", {
      name: "Pending Gmail 1",
    });
    fireEvent.click(pendingTab);

    const pendingTable = screen.getByRole("table");
    expect(within(pendingTable).getByText("Pending Profile")).toBeInTheDocument();
    expect(
      within(pendingTable).getByText("Profile in progress"),
    ).toBeInTheDocument();
    expect(
      within(pendingTable).queryByText("Round Wise Candidate"),
    ).not.toBeInTheDocument();
    expect(
      within(pendingTable).queryByText("Completed Profile"),
    ).not.toBeInTheDocument();

    fireEvent.click(
      within(pendingTable).getByRole("button", { name: "Link Gmail" }),
    );
    expect(screen.getByLabelText("Candidate Gmail owner")).toHaveValue(
      "profile-pending",
    );
    expect(screen.getByLabelText("Gmail address")).toHaveValue(
      "pending@example.com",
    );
  });
  it("autopopulates the selected candidate's saved email address", async () => {
    render(
      <ConfirmProvider>
        <RecruitmentMailPanel />
      </ConfirmProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Mailboxes" }));
    fireEvent.click(
      await screen.findByRole("button", { name: "+ Add candidate Gmail" }),
    );
    fireEvent.change(screen.getByLabelText("Candidate Gmail owner"), {
      target: { value: "c1" },
    });
    expect(screen.getByLabelText("Gmail address")).toHaveValue(
      "test.candidate@gmail.com",
    );
    expect(screen.getByRole("button", { name: "Connect Gmail" })).toBeEnabled();
  });
  it("keeps mailboxes attached to a legacy candidate alias visible", async () => {
    fetch.mockImplementation(async (url) => {
      const path = String(url);
      if (path.includes("/candidate-mailboxes/overview"))
        return {
          ok: true,
          json: async () => ({
            status: "ok",
            mailboxes: [
              {
                mailbox: {
                  id: "mailbox-legacy",
                  candidate_id: "legacy-candidate-row",
                  canonical_candidate_id: "c1",
                  email_address: "legacy-linked@gmail.com",
                  connection_status: "CONNECTED",
                  monitoring_enabled: true,
                },
                stats: { important_emails: 2, pending_reviews: 0 },
              },
            ],
          }),
        };
      return { ok: true, json: async () => payloadFor(path) };
    });

    render(
      <ConfirmProvider>
        <RecruitmentMailPanel />
      </ConfirmProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Mailboxes" }));

    expect(await screen.findByText("legacy-linked@gmail.com")).toBeInTheDocument();
    expect(
      screen.getByRole("cell", { name: /Test Candidate/ }),
    ).toBeInTheDocument();
  });
  it("keeps mailbox administration separate from mail review reporting", async () => {
    fetch.mockImplementation(async (url, options = {}) => {
      const path = String(url);
      if (path.includes("/candidate-mailboxes/overview")) {
        return {
          ok: true,
          json: async () => ({
            status: "ok",
            mailboxes: [
              {
                mailbox: {
                  id: "mailbox-relevant",
                  candidate_id: "c1",
                  email_address: "relevant@gmail.com",
                  connection_status: "CONNECTED",
                  monitoring_enabled: true,
                },
                stats: { important_emails: 3, pending_reviews: 0 },
              },
              {
                mailbox: {
                  id: "mailbox-review",
                  candidate_id: "c1",
                  email_address: "review@gmail.com",
                  connection_status: "CONNECTED",
                  monitoring_enabled: true,
                },
                stats: { important_emails: 0, pending_reviews: 1 },
              },
            ],
          }),
        };
      }
      return { ok: true, json: async () => payloadFor(path) };
    });
    render(
      <ConfirmProvider>
        <RecruitmentMailPanel />
      </ConfirmProvider>,
    );
    await screen.findByText("relevant@gmail.com");
    expect(screen.getByText("review@gmail.com")).toBeInTheDocument();
    expect(
      screen.queryByRole("columnheader", { name: "Relevant Emails" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("columnheader", { name: "Needs Review" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "View Emails" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getAllByLabelText(/More actions for Test Candidate/),
    ).toHaveLength(2);
  });
  it("shows action confirmation and live sync progress for a mailbox", async () => {
    let syncRequested = false;
    fetch.mockImplementation(async (url, options = {}) => {
      const path = String(url);
      if (path.includes("/api/candidates/c1/mailbox/sync")) {
        syncRequested = true;
        return {
          ok: true,
          json: async () => ({ status: "ok", job: { status: "QUEUED" } }),
        };
      }
      if (path.includes("/candidate-mailboxes/overview")) {
        return {
          ok: true,
          json: async () => ({
            status: "ok",
            mailboxes: [
              {
                mailbox: {
                  id: "m1",
                  candidate_id: "c1",
                  email_address: "candidate@gmail.com",
                  connection_status: "CONNECTED",
                  monitoring_enabled: true,
                },
                stats: {
                  latest_sync_status: syncRequested ? "QUEUED" : "COMPLETED",
                },
              },
            ],
          }),
        };
      }
      return { ok: true, json: async () => payloadFor(path) };
    });
    render(
      <ConfirmProvider>
        <RecruitmentMailPanel />
      </ConfirmProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Mailboxes" }));
    await screen.findByText("candidate@gmail.com");
    fireEvent.click(screen.getByRole("button", { name: "Sync Now" }));
    await waitFor(() =>
      expect(screen.getByText(/mailbox sync is queued/i)).toBeInTheDocument(),
    );
    expect(screen.getByText("Sync Queued")).toBeInTheDocument();
    expect(screen.getByText("Waiting to start…")).toBeInTheDocument();
  });
  it("defensively hides historical zero-percent recommendations", () => {
    expect(
      shouldShowInSelectionOfferReview({
        primary_status: "MANUAL_REVIEW_REQUIRED",
        confidence: 0,
        review_status: "PENDING",
        visible_in_offer_review: true,
        subject: "Job recommendations for you | foundit (Monster)",
        structured_result: {
          is_selection_or_offer_related: false,
          evidence: [],
        },
      }),
    ).toBe(false);
  });
  it("keeps strong manual offer evidence at 80 percent or more", () => {
    expect(
      shouldShowInSelectionOfferReview({
        primary_status: "MANUAL_REVIEW_REQUIRED",
        confidence: 0.85,
        review_status: "PENDING",
        visible_in_offer_review: true,
        structured_result: {
          is_selection_or_offer_related: true,
          evidence: [
            { meaning: "OFFER_INDICATION", text: "we are pleased to offer" },
          ],
        },
      }),
    ).toBe(true);
  });

  const retryPendingEvent = {
    id: "event-retry-1",
    candidate_id: "c1",
    subject: "Reminder: Don't Forget to attend these Walk-in's today",
    primary_status: "MANUAL_REVIEW_REQUIRED",
    review_status: "PENDING",
    validation_status: "RETRY_PENDING",
    ai_status: "RETRY_PENDING",
    ai_model: "unavailable:ollama_connection_failed",
    confidence: 0,
    visible_in_offer_review: true,
    created_at: "2026-07-18T13:38:53Z",
    structured_result: { evidence: [], validation_status: "RETRY_PENDING" },
  };

  it("shows a dated interview confirmation in the Review Queue", async () => {
    const interviewEvent = {
      id: "event-interview-confirmed-1",
      candidate_id: "c1",
      subject: "Virtual Interview - Senior Full Stack Engineer",
      primary_status: "INTERVIEW_CONFIRMED",
      review_status: "PENDING",
      validation_status: "RETRY_PENDING",
      ai_status: "RETRY_PENDING",
      ai_model: "unavailable:ollama_request_timeout",
      confidence: 0.8,
      visible_in_offer_review: true,
      created_at: "2026-07-20T14:44:00Z",
      structured_result: {
        evidence: [
          {
            source: "EMAIL_BODY",
            meaning: "INTERVIEW_CONFIRMED",
            text: "Please join the virtual interview at 12:30 PM on 21 July 2026",
          },
        ],
        interview: { date: "2026-07-21", time: "12:30 PM" },
        validation_status: "RETRY_PENDING",
      },
      received_email: {
        subject: "Virtual Interview - Senior Full Stack Engineer",
        sender_name: "Supriya Vithanala",
        sender_email: "recruiter@example.com",
        recipient_email: "test.candidate@gmail.com",
        sent_at: "2026-07-20T14:44:00Z",
        body: "Please join the virtual interview at 12:30 PM on 21 July 2026 using Microsoft Teams.",
      },
    };
    fetch.mockImplementation(async (url) => {
      const path = String(url);
      if (path.includes(`/events/${interviewEvent.id}`))
        return {
          ok: true,
          json: async () => ({ status: "ok", event: interviewEvent }),
        };
      if (path.includes("/review"))
        return {
          ok: true,
          json: async () => ({ status: "ok", events: [interviewEvent] }),
        };
      return { ok: true, json: async () => payloadFor(path) };
    });
    render(
      <ConfirmProvider>
        <RecruitmentMailPanel />
      </ConfirmProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Review Queue" }));
    await screen.findByText(interviewEvent.subject);
    expect(screen.getByText("Interview Confirmed")).toBeInTheDocument();
    expect(screen.getByText("1 records")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Approve & Book" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Approve" }),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Evidence" }));
    await screen.findByRole("heading", { name: "Complete email" });
    expect(screen.getByText(/2026-07-21.*12:30 PM/)).toBeInTheDocument();
    expect(
      screen.getAllByText(/Please join the virtual interview at 12:30 PM/),
    ).toHaveLength(2);
  });

  it("resolves the candidate name via canonical_candidate_id when candidate_id is a stale alias", async () => {
    const staleAliasEvent = {
      ...retryPendingEvent,
      id: "event-stale-alias-1",
      candidate_id: "f73cc8f464",
      canonical_candidate_id: "c1",
      subject: "You have a new job in your inbox!",
    };
    fetch.mockImplementation(async (url) => {
      const path = String(url);
      if (path.includes("/review"))
        return {
          ok: true,
          json: async () => ({ status: "ok", events: [staleAliasEvent] }),
        };
      return { ok: true, json: async () => payloadFor(path) };
    });
    render(
      <ConfirmProvider>
        <RecruitmentMailPanel />
      </ConfirmProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Review Queue" }));
    await screen.findByText(staleAliasEvent.subject);
    expect(
      screen.getByRole("cell", { name: /Test Candidate/ }),
    ).toBeInTheDocument();
    expect(screen.queryByText("f73cc8f464")).not.toBeInTheDocument();
  });

  it("filters the Review Queue to matching statuses when a summary tile is clicked", async () => {
    const joinedEvent = {
      id: "event-joined-1",
      candidate_id: "c2",
      subject: "Welcome aboard!",
      primary_status: "JOINED",
      review_status: "PENDING",
      validation_status: "NEEDS_REVIEW",
      ai_status: "ANALYZED",
      ai_model: "qwen3.6",
      confidence: 0.95,
      visible_in_offer_review: true,
      created_at: "2026-07-15T09:00:00Z",
      structured_result: {
        evidence: [
          { source: "EMAIL_BODY", meaning: "JOINED", text: "welcome aboard" },
        ],
      },
    };
    fetch.mockImplementation(async (url) => {
      const path = String(url);
      if (path.includes("/review"))
        return {
          ok: true,
          json: async () => ({
            status: "ok",
            events: [retryPendingEvent, joinedEvent],
          }),
        };
      return { ok: true, json: async () => payloadFor(path) };
    });
    render(
      <ConfirmProvider>
        <RecruitmentMailPanel />
      </ConfirmProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Selection & Offers" }));
    const needsReviewTile = screen
      .getByText("Needs Review", { selector: "h3" })
      .closest('[role="button"]');
    fireEvent.click(needsReviewTile);
    await screen.findByText(retryPendingEvent.subject);
    expect(screen.queryByText("Welcome aboard!")).not.toBeInTheDocument();
    expect(screen.getByText('Clear "Needs Review" filter')).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Selection & Offers" }));
    const joinedTile = screen
      .getByText("Joining", { selector: "h3" })
      .closest('[role="button"]');
    fireEvent.click(joinedTile);
    await screen.findByText("Welcome aboard!");
    expect(
      screen.queryByText(retryPendingEvent.subject),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Selection & Offers" }));
    const joinedTileAgain = screen
      .getByText("Joining", { selector: "h3" })
      .closest('[role="button"]');
    fireEvent.click(joinedTileAgain);
    await screen.findByText(retryPendingEvent.subject);
    expect(screen.getByText("Welcome aboard!")).toBeInTheDocument();
  });

  it("shows 'Pending AI' instead of a misleading 0% when AI never ran", async () => {
    fetch.mockImplementation(async (url) => {
      const path = String(url);
      if (path.includes("/review"))
        return {
          ok: true,
          json: async () => ({ status: "ok", events: [retryPendingEvent] }),
        };
      return { ok: true, json: async () => payloadFor(path) };
    });
    render(
      <ConfirmProvider>
        <RecruitmentMailPanel />
      </ConfirmProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Review Queue" }));
    await screen.findByText(retryPendingEvent.subject);
    expect(screen.getByText("Pending AI")).toBeInTheDocument();
    expect(screen.queryByText("0%")).not.toBeInTheDocument();
    const row = screen.getByText(retryPendingEvent.subject).closest("tr");
    expect(row).toHaveTextContent("Retry Pending");
    expect(row).toHaveTextContent("Ollama connection failed");
  });

  it("shows AI retry-pending details in Detection Evidence instead of staying stuck on Loading", async () => {
    fetch.mockImplementation(async (url) => {
      const path = String(url);
      if (path.includes("/review"))
        return {
          ok: true,
          json: async () => ({ status: "ok", events: [retryPendingEvent] }),
        };
      if (path.includes("/api/ai-recruitment/events/event-retry-1"))
        return {
          ok: true,
          json: async () => ({ status: "ok", event: retryPendingEvent }),
        };
      return { ok: true, json: async () => payloadFor(path) };
    });
    render(
      <ConfirmProvider>
        <RecruitmentMailPanel />
      </ConfirmProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Review Queue" }));
    await screen.findByText(retryPendingEvent.subject);
    fireEvent.click(screen.getByRole("button", { name: "Evidence" }));
    await screen.findByText(
      /AI analysis is pending because the AI service was unavailable/,
    );
    expect(screen.getByText("Ollama connection failed")).toBeInTheDocument();
    expect(screen.queryByText("Loading…")).not.toBeInTheDocument();
  });

  it("shows an error state with a working Retry button when the evidence API fails, never staying stuck on Loading", async () => {
    let evidenceCalls = 0;
    fetch.mockImplementation(async (url) => {
      const path = String(url);
      if (path.includes("/review"))
        return {
          ok: true,
          json: async () => ({ status: "ok", events: [retryPendingEvent] }),
        };
      if (path.includes("/api/ai-recruitment/events/event-retry-1")) {
        evidenceCalls += 1;
        if (evidenceCalls === 1) {
          return {
            ok: false,
            json: async () => ({ detail: "Event not found" }),
          };
        }
        return {
          ok: true,
          json: async () => ({ status: "ok", event: retryPendingEvent }),
        };
      }
      return { ok: true, json: async () => payloadFor(path) };
    });
    render(
      <ConfirmProvider>
        <RecruitmentMailPanel />
      </ConfirmProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Review Queue" }));
    await screen.findByText(retryPendingEvent.subject);
    fireEvent.click(screen.getByRole("button", { name: "Evidence" }));
    await screen.findByText("Unable to load detection evidence.");
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await screen.findByText(
      /AI analysis is pending because the AI service was unavailable/,
    );
  });
});
