import React from "react";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import EarningsBreakdown from "./EarningsBreakdown.jsx";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const fmt = (value) => `₹${Number(value).toLocaleString("en-IN")}`;

// Thrilok, Jul 2026: 45,000 earned and 40,000 paid before July leaves 5,000
// carried in, on top of a July that nets to zero.
const THRILOK = {
  name: "Thrilok",
  count: 4,
  commission_total: 27000,
  salary_total: 15000,
  auto_earnings_total: 42000,
  paid_out_total: 42000,
  recoveries_total: 0,
  prior_balance: 5000,
  prior_owed: 45000,
  prior_paid: 40000,
  prior_recoveries: 0,
  prior_months: ["2026-06"],
  net_payable: 5000,
};

async function openRow(performer) {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve({ status: "ok", candidates: [] }) }),
    ),
  );
  render(
    <EarningsBreakdown
      stats={{ top_performers: [performer] }}
      month="2026-07"
      formatCurrency={fmt}
      apiBase="/api"
    />,
  );
  const nameCell = screen.getAllByText(performer.name).find((el) => el.closest("tr.earn-row"));
  fireEvent.click(nameCell.closest("tr"));
  const strip = (await screen.findByText(/^Total \(/)).closest("li");
  return {
    strip,
    opening: within(strip).getByText("Opening balance").closest(".earn-summary-metric"),
  };
}

describe("opening balance states its reason", () => {
  it("names the month the balance was carried from", async () => {
    const { opening } = await openRow(THRILOK);
    expect(opening.textContent).toContain("unpaid from Jun 2026");
  });

  it("shows the earned/paid split behind the figure", async () => {
    const { opening } = await openRow(THRILOK);
    const note = opening.querySelector(".earn-summary-note");
    expect(note.getAttribute("title")).toBe("Earned ₹45,000 · paid ₹40,000 before Jul 2026");
  });

  it("names a range when several months contributed", async () => {
    const { opening } = await openRow({
      ...THRILOK,
      prior_months: ["2026-03", "2026-06"],
    });
    expect(opening.textContent).toContain("unpaid from Mar 2026 – Jun 2026");
  });

  it("includes recoveries in the explanation when there were any", async () => {
    const { opening } = await openRow({
      ...THRILOK,
      prior_recoveries: 3000,
      prior_balance: 2000,
      net_payable: 2000,
    });
    const note = opening.querySelector(".earn-summary-note");
    expect(note.getAttribute("title")).toContain("recovered ₹3,000");
  });

  it("says overpaid when the referrer carried a negative balance", async () => {
    const { opening } = await openRow({
      ...THRILOK,
      prior_balance: -5000,
      prior_paid: 50000,
      net_payable: -5000,
    });
    expect(opening.textContent).toContain("overpaid in Jun 2026");
  });

  it("still explains itself when the backend sent no months", async () => {
    const { opening } = await openRow({ ...THRILOK, prior_months: [] });
    expect(opening.textContent).toContain("unpaid from earlier months");
  });

  it("puts the same reason on the collapsed row's carry-forward chip", async () => {
    await openRow(THRILOK);
    const chip = document.querySelector(".earn-carry-fwd");
    expect(chip.getAttribute("title")).toContain("unpaid from Jun 2026");
    expect(chip.getAttribute("title")).toContain("Earned ₹45,000");
  });
});
