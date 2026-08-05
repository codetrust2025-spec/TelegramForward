import React from "react";
import { useCompactLayout } from "../utils/useCompactLayout.js";
import { OptionPickList } from "./ui/OptionPickList.jsx";

const MAIN_VIEWS = [
  { value: "dashboard", label: "Dashboard", shortLabel: "Dashboard" },
  { value: "inbox", label: "Inbox", shortLabel: "Inbox" },
  { value: "candidates", label: "Candidates", shortLabel: "Candidates" },
  { value: "knowledge", label: "Ask AI", shortLabel: "Ask AI" },
  { value: "ai-recruitment", label: "AI Mail Review", shortLabel: "AI Mail" },
  { value: "outcome-audit", label: "Mail Audit", shortLabel: "Audit" },
  { value: "data-room", label: "Data room", shortLabel: "Data" },
  { value: "admin", label: "Admin", shortLabel: "Admin" },
  { value: "logs", label: "Logs", shortLabel: "Logs" },
];

/**
 * Top-level app sections. Narrow: tap tiles; wide: tab buttons.
 */
const HANDLER_VIEWS = [
  { value: "handler-kit", label: "My kit", shortLabel: "Kit" },
  ...MAIN_VIEWS.filter((v) => v.value === "candidates"),
];

export function AppViewNav({
  mainView,
  onNavigate,
  inboxUnreadTotal = 0,
  inboxUnreadBadge = "",
  handlerMode = false,
  recruitmentEnabled = false,
}) {
  const compact = useCompactLayout();
  const views = handlerMode ? HANDLER_VIEWS : MAIN_VIEWS;

  const options = views.map((v) => ({
    value: v.value,
    label:
      v.value === "inbox" && inboxUnreadTotal > 0
        ? `Inbox (${inboxUnreadBadge})`
        : v.shortLabel,
  }));

  if (compact) {
    return (
      <nav
        className="app-view-nav-root app-view-nav-root--compact"
        aria-label="Main view"
      >
        <OptionPickList
          className="app-view-nav-picklist"
          label="Main view"
          options={options}
          value={mainView}
          onChange={onNavigate}
          columns={2}
        />
      </nav>
    );
  }

  return (
    <nav className="app-view-nav-root" aria-label="Main view">
      <div className="app-view-nav app-view-nav-buttons">
        {views.map((v) => {
          const isInbox = v.value === "inbox";
          const active = mainView === v.value;
          return (
            <button
              key={v.value}
              type="button"
              className={[
                "app-view-nav-btn",
                active ? "app-view-nav-btn--active" : "",
                isInbox && inboxUnreadTotal > 0
                  ? "app-view-nav-btn--has-unread"
                  : "",
              ]
                .filter(Boolean)
                .join(" ")}
              onClick={() => onNavigate(v.value)}
              aria-label={
                isInbox && inboxUnreadTotal > 0
                  ? `Inbox, ${inboxUnreadTotal} unread message${inboxUnreadTotal === 1 ? "" : "s"}`
                  : v.label
              }
              title={
                v.value === "data-room"
                  ? "Data room — partners and business opportunities"
                  : v.value === "admin"
                    ? "Karthik admin — monitoring and AI control"
                    : v.value === "logs"
                      ? "Live activity logs"
                      : v.value === "candidates"
                        ? "Candidates tracker"
                        : v.value === "outcome-audit"
                          ? "Candidate mail outcome audit — evidence-based, read-only"
                          : undefined
              }
            >
              {v.label}
              {isInbox && inboxUnreadTotal > 0 && (
                <span className="app-view-nav-badge" aria-hidden>
                  {inboxUnreadBadge}
                </span>
              )}
            </button>
          );
        })}
      </div>
    </nav>
  );
}
