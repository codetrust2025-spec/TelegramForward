/**
 * Every sidebar entry must actually go somewhere.
 *
 * Reconciliation and BGV Consultancy shipped visible but inert: the sidebar
 * listed them, App.jsx had routes for them, and both panels had their own
 * passing tests — but the desktop shell owns a second, separate dispatch, and
 * its switch had no case for either id. Clicking fell through to
 * `default: break`, so nothing happened at all. Panel tests could never catch
 * that, because nothing was ever asked to navigate to the panels.
 */

import React, { useState } from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DesktopApp } from "./DesktopApp.jsx";
import { NAV } from "./DesktopSidebar.jsx";
import DesktopAppSource from "./DesktopApp.jsx?raw";

// The pending-works context pulls in auth and react-query; navigation does not
// depend on it, so it is stubbed rather than stood up.
vi.mock("../dailyOps/PendingWorksProvider.jsx", async (importOriginal) => {
  const actual = await importOriginal();
  const ctx = {
    works: [],
    count: 0,
    candidateCount: 0,
    pendingInterviewCount: 0,
    pendingInterviews: [],
    loading: false,
    error: null,
  };
  return {
    ...actual,
    PendingWorksProvider: ({ children }) => children,
    usePendingWorksContext: () => ctx,
    usePendingWorksContextOptional: () => ctx,
  };
});

const EMPTY_RECON = { status: "ok", profiles_checked: 0, counts: {}, records: [] };
const EMPTY_BGV = { status: "ok", total_cases: 0, cases: [] };

function respond(url) {
  const body = String(url).includes("/bgv/") ? EMPTY_BGV : EMPTY_RECON;
  return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) });
}

/** Holds mainView so a sidebar click actually re-renders, as the real app does. */
function Harness() {
  const [mainView, setMainView] = useState("dashboard");
  const [desktopPage, setDesktopPage] = useState("home");
  const [workspaceMode, setWorkspaceMode] = useState("fleet");
  return (
    <DesktopApp
      mainView={mainView}
      setMainView={setMainView}
      desktopPage={desktopPage}
      setDesktopPage={setDesktopPage}
      workspaceMode={workspaceMode}
      setWorkspaceMode={setWorkspaceMode}
      connected
      fleet={{ perAccount: [] }}
      state={{
        account_info: {},
        active_account: null,
        daily_stats: {},
        accounts: [],
      }}
      recentLogs={[]}
      loggedInSlots={[]}
      postingModes={{}}
      inboxProps={{}}
      logsProps={{}}
      progressHubProps={{}}
      setupPanelProps={{}}
      modesProps={{}}
    />
  );
}

describe("desktop sidebar navigation", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn((url) => respond(url)));
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("opens Reconciliation from the sidebar", async () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: /Reconciliation/i }));
    await waitFor(() =>
      expect(screen.getByText(/Payment Reconciliation/i)).toBeTruthy(),
    );
  });

  it("opens BGV Consultancy from the sidebar", async () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: /BGV Consultancy/i }));
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: /BGV Consultancy/i })).toBeTruthy(),
    );
  });

  it("marks the clicked entry active, so it never looks unresponsive", async () => {
    render(<Harness />);
    const link = screen.getByRole("button", { name: /Reconciliation/i });
    fireEvent.click(link);
    await waitFor(() =>
      expect(
        screen
          .getByRole("button", { name: /Reconciliation/i })
          .className.includes("desktop-sidebar__link--active"),
      ).toBe(true),
    );
  });

  it("leaves no sidebar entry without a dispatch case", () => {
    // Structural guard rather than a render sweep: the defect was an id the
    // shell's switch never mentioned, and that is checkable directly without
    // standing up every panel in the app.
    const missing = NAV.filter(
      (item) => !item.external && !DesktopAppSource.includes(`case "${item.id}":`),
    ).map((item) => item.id);
    expect(missing).toEqual([]);
  });
});
