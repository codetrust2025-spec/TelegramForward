import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CallOutcomeModal } from "./crm/CallOutcomeModal.jsx";
import { focusableWithin } from "../hooks/useDialogA11y.js";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

/**
 * An audit of every role="dialog" in this app found focus restoration and a
 * Tab trap in exactly one place: CommonModal. These cases pin the behaviour
 * the shared hook now gives the hand-written dialogs.
 */
describe("CallOutcomeModal accessibility", () => {
  const open = (props = {}) =>
    render(
      <div>
        <button type="button">Trigger</button>
        <CallOutcomeModal open leadName="Raju" onSelect={() => {}} onDismiss={() => {}} {...props} />
      </div>,
    );

  it("is a modal dialog with an accessible name", () => {
    open();
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAttribute("aria-labelledby", "call-outcome-title");
    expect(document.getElementById("call-outcome-title")).toHaveTextContent("Mark call outcome");
  });

  it("moves focus into the dialog when it opens", async () => {
    open();
    const dialog = screen.getByRole("dialog");
    await vi.waitFor(() => expect(dialog.contains(document.activeElement)).toBe(true));
  });

  it("closes on Escape", () => {
    const onDismiss = vi.fn();
    open({ onDismiss });
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("wraps Tab from the last control back to the first", () => {
    open();
    const items = focusableWithin(screen.getByRole("dialog"));
    expect(items.length).toBeGreaterThan(1);
    items[items.length - 1].focus();
    fireEvent.keyDown(document, { key: "Tab" });
    expect(document.activeElement).toBe(items[0]);
  });

  it("wraps Shift+Tab from the first control back to the last", () => {
    open();
    const items = focusableWithin(screen.getByRole("dialog"));
    items[0].focus();
    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(items[items.length - 1]);
  });

  it("keeps focus out of the background while open", () => {
    open();
    screen.getByText("Trigger").focus();
    fireEvent.keyDown(document, { key: "Tab" });
    expect(screen.getByRole("dialog").contains(document.activeElement)).toBe(true);
  });
});

describe("every hand-written dialog declares itself properly", () => {
  // Read the sources rather than mounting each: several need heavy props or a
  // live socket, and the declaration is what regresses.
  const files = import.meta.glob(
    [
      "./crm/CallNowModal.jsx",
      "./crm/CallOutcomeModal.jsx",
      "./crm/ScheduleCallModal.jsx",
      "./ChangePasswordModal.jsx",
      "../inbox/InboxMarketingMessageModal.jsx",
      "../candidates/PayoutModal.jsx",
      "../admin/adminModule.jsx",
    ],
    { query: "?raw", import: "default", eager: true },
  );

  const entries = Object.entries(files);

  it("covers every dialog in the audit list", () => {
    expect(entries.length).toBe(7);
  });

  it.each(entries)("%s marks itself aria-modal", (_name, source) => {
    expect(source).toContain('aria-modal="true"');
  });

  it.each(entries)("%s has an accessible name", (_name, source) => {
    expect(source).toMatch(/aria-labelledby=|aria-label=/);
  });

  it.each(entries)("%s uses the shared focus manager", (_name, source) => {
    expect(source).toContain("useDialogA11y");
    expect(source).toContain("ref={dialogRef}");
  });

  it.each(entries)("%s gives its close control an accessible label", (name, source) => {
    // Either an explicit aria-label or visible text on the close control.
    const hasLabelled = /aria-label="Close"|aria-label='Close'/.test(source);
    const hasTextual = /Close|Cancel|Dismiss|Not now/.test(source);
    expect(hasLabelled || hasTextual, `${name} close control`).toBe(true);
  });
});
