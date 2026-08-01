import React from "react";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import EarningsBreakdown from "./EarningsBreakdown.jsx";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const fmt = (value) => `₹${Number(value).toLocaleString("en-IN")}`;

/**
 * The expanded summary strip has to add up on screen:
 *
 *   opening + earnings − recoveries − expenses = closing
 *
 * The backend computes closing as
 * `(commission + salary) − recoveries − paid_out + prior_balance`
 * (features/candidate_store.py). The strip used to print commission alone as
 * "Earnings" and omit recoveries entirely, so a referrer on a salary saw a row
 * that contradicted its own closing balance.
 */
async function renderStrip(performer) {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ status: "ok", candidates: [] }) })),
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
  return await screen.findByText(/^Total \(/).then((el) => el.closest("li"));
}

function amountFor(strip, label) {
  const metric = within(strip).getByText(label).closest(".earn-summary-metric");
  return metric.querySelector("strong").textContent;
}

function toNumber(text) {
  const negative = text.startsWith("−") || text.startsWith("-");
  const digits = Number(text.replace(/[^0-9]/g, "")) || 0;
  return negative ? -digits : digits;
}

describe("earnings summary strip reconciles with the closing balance", () => {
  // Thrilok, Jul 2026: commission 27,000 + salary 15,000 = 42,000 owed,
  // 42,000 paid out, 5,000 carried in. Closing must stay +5,000.
  const SALARIED = {
    name: "Thrilok",
    count: 4,
    completed: 0,
    revenue_total: 54000,
    commission_total: 27000,
    salary_total: 15000,
    auto_earnings_total: 42000,
    paid_out_total: 42000,
    recoveries_total: 0,
    prior_balance: 5000,
    net_payable: 5000,
  };

  it("counts salary in Earnings so the arithmetic holds", async () => {
    const strip = await renderStrip(SALARIED);

    expect(amountFor(strip, "Earnings")).toBe(fmt(42000));

    const opening = toNumber(amountFor(strip, "Opening balance"));
    const earnings = toNumber(amountFor(strip, "Earnings"));
    const expenses = toNumber(amountFor(strip, "Expenses"));
    const closing = toNumber(amountFor(strip, "Closing balance"));

    expect(opening + earnings + expenses).toBe(closing);
    expect(closing).toBe(5000);
  });

  it("says which part of Earnings is salary", async () => {
    const strip = await renderStrip(SALARIED);
    expect(within(strip).getByText(/incl\. ₹15,000 salary/)).toBeInTheDocument();
  });

  it("omits the salary note when the referrer has no salary", async () => {
    const strip = await renderStrip({
      ...SALARIED,
      salary_total: 0,
      auto_earnings_total: 27000,
      paid_out_total: 27000,
    });
    expect(within(strip).queryByText(/salary/)).toBeNull();
    expect(amountFor(strip, "Earnings")).toBe(fmt(27000));
  });

  it("shows recoveries as a deduction and still reconciles", async () => {
    const strip = await renderStrip({
      ...SALARIED,
      recoveries_total: 3000,
      // (27000 + 15000) − 3000 − 42000 + 5000
      net_payable: 2000,
    });

    expect(amountFor(strip, "Recoveries")).toBe("−₹3,000");

    const total =
      toNumber(amountFor(strip, "Opening balance")) +
      toNumber(amountFor(strip, "Earnings")) +
      toNumber(amountFor(strip, "Recoveries")) +
      toNumber(amountFor(strip, "Expenses"));
    expect(total).toBe(toNumber(amountFor(strip, "Closing balance")));
  });

  it("hides the recoveries metric when there are none", async () => {
    const strip = await renderStrip(SALARIED);
    expect(within(strip).queryByText("Recoveries")).toBeNull();
  });

  it("labels the total 'Net balance' when nothing was carried in", async () => {
    const strip = await renderStrip({
      ...SALARIED,
      prior_balance: 0,
      net_payable: 0,
    });
    expect(within(strip).getByText("Net balance")).toBeInTheDocument();
    expect(within(strip).queryByText("Opening balance")).toBeNull();
  });
});
