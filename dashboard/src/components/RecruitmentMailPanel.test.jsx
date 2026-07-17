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
  if (url.includes("/dashboard"))
    return {
      status: "ok",
      metrics: { selections_detected: 1 },
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
    expect(screen.getByPlaceholderText("candidate@gmail.com")).toHaveAttribute(
      "type",
      "email",
    );
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
});
