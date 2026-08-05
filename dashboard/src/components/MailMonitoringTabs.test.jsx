import React from "react";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MailMonitoringTabs } from "./MailMonitoringTabs.jsx";

const SRC = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const read = (rel) => fs.readFileSync(path.join(SRC, rel), "utf8");

afterEach(cleanup);

describe("AI mail monitoring sub-navigation", () => {
  it("offers both sections", () => {
    render(<MailMonitoringTabs active="mail-notifications" />);
    expect(screen.getByText("Notifications")).toBeTruthy();
    expect(screen.getByText("Mail Audit")).toBeTruthy();
  });

  it("marks the current section for assistive technology", () => {
    render(<MailMonitoringTabs active="outcome-audit" />);
    expect(screen.getByText("Mail Audit").getAttribute("aria-current")).toBe("page");
    expect(screen.getByText("Notifications").getAttribute("aria-current")).toBeNull();
  });

  it("navigates to the audit view on the app's own event bus", () => {
    const seen = [];
    const listener = (event) => seen.push(event.detail?.view);
    window.addEventListener("teleautomation:navigate", listener);
    render(<MailMonitoringTabs active="mail-notifications" />);
    fireEvent.click(screen.getByText("Mail Audit"));
    window.removeEventListener("teleautomation:navigate", listener);
    expect(seen).toEqual(["outcome-audit"]);
  });

  it("does not re-navigate to the section already open", () => {
    const seen = [];
    const listener = (event) => seen.push(event.detail?.view);
    window.addEventListener("teleautomation:navigate", listener);
    render(<MailMonitoringTabs active="outcome-audit" />);
    fireEvent.click(screen.getByText("Mail Audit"));
    window.removeEventListener("teleautomation:navigate", listener);
    expect(seen).toEqual([]);
  });
});

/**
 * The audit shipped to Production three times before it was reachable. The app
 * has more than one shell — App.jsx renders MobileApp or DesktopApp, and the
 * DesktopApp sidebar is the navigation an administrator actually sees — so
 * wiring one of them proves nothing about the others.
 *
 * The first test below is the general one: every shell that can navigate to
 * AI Mail Review must also navigate to Mail Audit. A fourth shell added later
 * fails here on the day it is added rather than after a deploy.
 */
function shellFiles() {
  return walk(SRC)
    .map((full) => ({
      rel: path.relative(SRC, full).split(path.sep).join("/"),
      text: fs.readFileSync(full, "utf8"),
    }))
    // A shell is any module that both routes a main view and offers the
    // sibling AI Mail Review destination.
    .filter((f) => /mainView\s*===\s*["']ai-recruitment["']/.test(f.text));
}

function walk(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) return walk(full);
    if (!entry.name.endsWith(".jsx") || entry.name.includes(".test.")) return [];
    return [full];
  });
}

describe("Mail Audit is reachable from every shell", () => {
  it("every shell that routes AI Mail Review also routes Mail Audit", () => {
    const shells = shellFiles();
    expect(shells.length).toBeGreaterThan(0);
    const missing = shells
      .filter((f) => !/mainView\s*===\s*["']outcome-audit["']/.test(f.text))
      .map((f) => f.rel);
    expect(missing).toEqual([]);
  });

  it("is in the desktop sidebar, directly below AI Mail Review", () => {
    const sidebar = read("desktop/DesktopSidebar.jsx");
    expect(sidebar).toContain('id: "outcome-audit"');
    expect(sidebar).toContain('label: "Mail Audit"');
    // Order matters: the operator asked for it beneath AI Mail Review.
    expect(sidebar.indexOf('id: "ai-recruitment"')).toBeLessThan(
      sidebar.indexOf('id: "outcome-audit"'),
    );
    // Rendered unconditionally — no role or workspace gate on the nav list.
    expect(sidebar).toContain("NAV.map((item)");
  });

  it("is routed and highlighted by the desktop shell", () => {
    const desktop = read("desktop/DesktopApp.jsx");
    expect(desktop).toContain("OutcomeAuditPanel");
    expect(desktop).toContain('mainView === "outcome-audit"');
    expect(desktop).toContain('case "outcome-audit":');
    // sidebarActiveId must return the id or the link never shows as active.
    expect(desktop).toContain('return "outcome-audit"');
  });

  it("is routed by the mobile shell", () => {
    const mobile = read("mobile/MobileApp.jsx");
    expect(mobile).toContain("OutcomeAuditPanel");
    expect(mobile).toContain('mainView === "outcome-audit"');
    // Listed in the menu, mapped to a nav group, and handled on selection.
    expect(mobile).toContain('id: "outcome-audit"');
    expect(mobile).toContain('case "outcome-audit":');
  });

  it("is linked from the notifications page and back", () => {
    expect(read("components/MailMonitoringNotifications.jsx")).toContain(
      'MailMonitoringTabs active="mail-notifications"',
    );
    expect(read("components/OutcomeAuditPanel.jsx")).toContain(
      'MailMonitoringTabs active="outcome-audit"',
    );
  });

  it("keeps the main nav from clipping a section out of view", () => {
    // Without wrapping, the ninth section is painted outside an
    // overflow:hidden shell and cannot be reached by any means.
    expect(read("responsive.css")).toMatch(
      /\.app-header \.app-view-nav[^}]*flex-wrap:\s*wrap/s,
    );
  });
});
