import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RecruitmentMailPanel, shouldShowInSelectionOfferReview } from "./RecruitmentMailPanel.jsx";
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
      candidates: [{ id: "c1", name: "Test Candidate", phone: "9000000000" }],
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
  afterEach(() => vi.unstubAllGlobals());
  it("renders dashboard metrics and the review empty state", async () => {
    render(
      <ConfirmProvider>
        <RecruitmentMailPanel />
      </ConfirmProvider>,
    );
    expect(
      screen.getByRole("heading", { name: "Selection and Offer Review" }),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.getByText("No important detections match the filters."),
      ).toBeInTheDocument(),
    );
    expect(
      screen.getByText("Candidates selected").parentElement,
    ).toHaveTextContent("1");
  });
  it("defensively hides historical zero-percent recommendations", () => {
    expect(shouldShowInSelectionOfferReview({
      primary_status: "MANUAL_REVIEW_REQUIRED", confidence: 0,
      review_status: "PENDING", visible_in_offer_review: true,
      subject: "Job recommendations for you | foundit (Monster)",
      structured_result: { is_selection_or_offer_related: false, evidence: [] },
    })).toBe(false);
  });
  it("keeps strong manual offer evidence at 80 percent or more", () => {
    expect(shouldShowInSelectionOfferReview({
      primary_status: "MANUAL_REVIEW_REQUIRED", confidence: .85,
      review_status: "PENDING", visible_in_offer_review: true,
      structured_result: { is_selection_or_offer_related: true, evidence: [
        { meaning: "OFFER_INDICATION", text: "we are pleased to offer" },
      ] },
    })).toBe(true);
  });
});
