import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RecruitmentMailPanel } from "./RecruitmentMailPanel.jsx";
import { ConfirmProvider } from "../context/ConfirmContext.jsx";

const payloadFor = (url) => {
  if (url.includes("/dashboard"))
    return {
      status: "ok",
      metrics: { connected_mailboxes: 1 },
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
      screen.getByRole("heading", { name: "AI Selection and Offer Review" }),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.getByText("No detections match the filters."),
      ).toBeInTheDocument(),
    );
    expect(
      screen.getByText("Connected mailboxes").parentElement,
    ).toHaveTextContent("1");
  });
});
