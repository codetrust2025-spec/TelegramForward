import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

/**
 * Every `role="dialog"` in the app must get its focus management from one of
 * two places: CommonModal, or the shared useDialogA11y hook. A dialog that
 * rolls its own behaviour leaves focus on the page behind it, lets Tab walk
 * out into the background, and drops focus to <body> when it closes.
 *
 * This test enumerates the source rather than any one component, so a new
 * hand-written dialog fails here on the day it is added instead of being
 * found by the next audit.
 */
const SRC = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

// Dialogs not yet migrated. Each entry is a promise to come back to it; the
// count is asserted below so the list can only shrink without a deliberate
// edit. Removing a file from here is what "migrated" means.
const NOT_YET_MIGRATED = new Set([
  "candidates/CandidatesActiveRoster.jsx",
  "candidates/candidatesModule.jsx",
  "components/KnowledgeAssistantPanel.jsx",
  "dailyOps/DailyOpsPanel.jsx",
  "dailyOps/InterviewRoster.jsx",
  "desktop/ForwarderConsole.jsx",
  "inbox/InboxDemoTools.jsx",
  "inbox/OutgoingCallOverlay.jsx",
  "mobile/MobileApp.jsx",
  "mobile/MobileDashboardHome.jsx",
  "pages/TwelveHourTimePicker.jsx",
  "teleautomation-app.jsx",
]);

function walk(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) return walk(full);
    if (!entry.name.endsWith(".jsx") || entry.name.includes(".test.")) return [];
    return [full];
  });
}

function dialogFiles() {
  return walk(SRC)
    .map((full) => ({
      rel: path.relative(SRC, full).split(path.sep).join("/"),
      text: fs.readFileSync(full, "utf8"),
    }))
    .filter((file) => file.text.includes('role="dialog"'));
}

describe("dialog focus management coverage", () => {
  it("every dialog uses CommonModal or the shared hook, or is a named exception", () => {
    const rogue = dialogFiles()
      .filter((f) => !f.text.includes("useDialogA11y") && !f.text.includes("CommonModal"))
      .map((f) => f.rel)
      .filter((rel) => !NOT_YET_MIGRATED.has(rel));
    expect(rogue).toEqual([]);
  });

  it("the exception list only shrinks", () => {
    // Raising this number means a dialog was added without focus management.
    expect(NOT_YET_MIGRATED.size).toBeLessThanOrEqual(12);
  });

  it("every listed exception still exists and still holds a dialog", () => {
    // A stale entry would silently excuse a file that no longer needs it.
    const present = new Set(dialogFiles().map((f) => f.rel));
    const stale = [...NOT_YET_MIGRATED].filter((rel) => !present.has(rel));
    expect(stale).toEqual([]);
  });

  it("a migrated dialog declares itself modal and carries a name", () => {
    const missing = dialogFiles()
      .filter((f) => f.text.includes("useDialogA11y"))
      .filter((f) => !f.text.includes("aria-modal")
        || !(f.text.includes("aria-label") || f.text.includes("aria-labelledby")))
      .map((f) => f.rel);
    expect(missing).toEqual([]);
  });

  it("a migrated dialog attaches the ref the hook returns", () => {
    // Importing the hook without wiring its ref traps nothing.
    const unattached = dialogFiles()
      .filter((f) => f.text.includes("useDialogA11y"))
      .filter((f) => !/ref=\{[A-Za-z]*[dD]ialogRef\}/.test(f.text))
      .map((f) => f.rel);
    expect(unattached).toEqual([]);
  });
});
