import React from "react";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
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
  if (url.includes("/candidates?"))
    return {
      status: "ok",
      candidates: [
        {
          id: "c1",
          name: "Test Candidate",
          phone: "9000000000",
          email: "test.candidate@gmail.com",
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
  it("renders the redesigned tracking dashboard with mailboxes selected", async () => {
    render(
      <ConfirmProvider>
        <RecruitmentMailPanel />
      </ConfirmProvider>,
    );
    expect(
      screen.getByRole("heading", { name: "Selection & Offer Tracking" }),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "Mailbox Overview" }),
      ).toBeInTheDocument(),
    );
    expect(screen.getByText("Selected").closest("article")).toHaveTextContent(
      "1",
    );
    expect(
      screen.getByText("Joining Confirmed").closest("article"),
    ).toHaveTextContent("5");
    expect(screen.getByText("Joined").closest("article")).toHaveTextContent(
      "0",
    );
    expect(screen.getByRole("button", { name: "Mailboxes" })).toHaveClass(
      "active",
    );
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
    fireEvent.click(screen.getByRole("button", { name: "Candidates" }));
    await waitFor(() =>
      expect(
        screen.getByRole("option", { name: /Test Candidate/ }),
      ).toBeInTheDocument(),
    );
    expect(screen.queryByText("Request failed")).not.toBeInTheDocument();
  });
  it("refreshes Ollama health without reloading the page", async () => {
    render(
      <ConfirmProvider>
        <RecruitmentMailPanel />
      </ConfirmProvider>,
    );
    expect(await screen.findByText("AI Available")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Refresh/ }));
    await waitFor(() =>
      expect(
        fetch.mock.calls.some(([url]) =>
          String(url).includes("/ollama/status?refresh=true&_="),
        ),
      ).toBe(true),
    );
    expect(screen.getByText(/Last updated:/)).not.toHaveTextContent("Loading");
  });
  it("offers an add candidate Gmail form for candidates without a mailbox", async () => {
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
    expect(
      screen.getByRole("option", { name: /Test Candidate/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText(/^candidate@gmail\.com/),
    ).toHaveAttribute("type", "email");
    expect(
      screen.getByRole("button", { name: "Connect Gmail" }),
    ).toBeDisabled();
  });
  it("autopopulates the selected candidate's saved email address", async () => {
    render(
      <ConfirmProvider>
        <RecruitmentMailPanel />
      </ConfirmProvider>,
    );
    fireEvent.click(
      await screen.findByRole("button", { name: "+ Add candidate Gmail" }),
    );
    fireEvent.change(screen.getByLabelText("Candidate"), {
      target: { value: "c1" },
    });
    expect(screen.getByLabelText("Gmail address")).toHaveValue(
      "test.candidate@gmail.com",
    );
    expect(screen.getByRole("button", { name: "Connect Gmail" })).toBeEnabled();
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
      if (
        path.includes("/api/candidates/c1/mailbox") &&
        (!options.method || options.method === "GET")
      ) {
        return {
          ok: true,
          json: async () => ({
            status: "ok",
            mailbox: {
              id: "m1",
              email_address: "candidate@gmail.com",
              connection_status: "CONNECTED",
              monitoring_enabled: true,
            },
            stats: {
              latest_sync_status: syncRequested ? "QUEUED" : "COMPLETED",
            },
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
    expect(screen.getByText("Test Candidate")).toBeInTheDocument();
    expect(screen.queryByText("f73cc8f464")).not.toBeInTheDocument();
  });

  it("filters the Review Queue to matching statuses when a summary tile is clicked", async () => {
    const joinedEvent = {
      id: "event-joined-1",
      candidate_id: "c2",
      subject: "Welcome aboard!",
      primary_status: "JOINED",
      review_status: "APPROVED",
      validation_status: "AUTO_VALIDATED",
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
    const needsReviewTile = screen
      .getByText("Needs Review", { selector: "h3" })
      .closest('[role="button"]');
    fireEvent.click(needsReviewTile);
    await screen.findByText(retryPendingEvent.subject);
    expect(screen.queryByText("Welcome aboard!")).not.toBeInTheDocument();
    expect(
      screen.getByText('Clear "Needs Review" filter'),
    ).toBeInTheDocument();

    const joinedTile = screen
      .getByText("Joined", { selector: "h3" })
      .closest('[role="button"]');
    fireEvent.click(joinedTile);
    await screen.findByText("Welcome aboard!");
    expect(
      screen.queryByText(retryPendingEvent.subject),
    ).not.toBeInTheDocument();

    fireEvent.click(joinedTile);
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
          return { ok: false, json: async () => ({ detail: "Event not found" }) };
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
