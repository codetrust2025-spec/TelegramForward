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
 * The audit shipped to Production and was unreachable: the top-level nav is a
 * fixed-width flex row inside an overflow:hidden shell, and the mobile shell
 * had no case for the view at all. These assert the wiring rather than the
 * rendering, so a future refactor that drops one of them fails here.
 */
describe("Mail Audit is reachable from every shell", () => {
  it("is a top-level view in the desktop nav", () => {
    expect(read("components/AppViewNav.jsx")).toContain('value: "outcome-audit"');
  });

  it("is routed by the desktop App", () => {
    const app = read("App.jsx");
    expect(app).toContain("OutcomeAuditPanel");
    expect(app).toContain("mainView === 'outcome-audit'");
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
