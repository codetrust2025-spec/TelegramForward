import React, { useEffect, useRef, useState } from "react";
import { usePendingWorksContextOptional } from "../dailyOps/PendingWorksProvider.jsx";

const NAV = [
  { id: "knowledge", label: "Ask AI", icon: "AI" },
  { id: "daily-briefing", label: "Daily briefing", icon: "☀" },
  { id: "ai-recruitment", label: "AI Mail Review", icon: "AI" },
  { id: "outcome-audit", label: "Mail Audit", icon: "🔍" },
  { id: "mail-notifications", label: "Mail alerts", icon: "🔔" },
  { id: "dashboard", label: "Dashboard", icon: "▣" },
  { id: "accounts", label: "Accounts", icon: "👤" },
  { id: "forwarding", label: "Forwarding", icon: "↻" },
  { id: "campaigns", label: "Campaigns", icon: "📣" },
  { id: "inbox", label: "Inbox", icon: "✉", badgeKey: "inbox" },
  {
    id: "candidates",
    label: "Candidates",
    icon: "📇",
    badgeKey: "pendingWorks",
  },
  {
    id: "daily-ops",
    label: "Daily ops",
    icon: "📅",
    badgeKey: "pendingInterviews",
  },
  { id: "data", label: "Data", icon: "📊" },
  { id: "logs", label: "Logs", icon: "📋" },
  { id: "admin", label: "Admin", icon: "⚙" },
  { id: "settings", label: "Settings", icon: "⚙" },
  {
    id: "slot-booking",
    label: "Slot booking",
    icon: "calendar",
    external: "/submit-slot",
  },
];

function NavIcon({ icon }) {
  if (icon === "calendar") {
    return (
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <rect x="3" y="4" width="18" height="18" rx="2" />
        <path d="M16 2v4M8 2v4M3 10h18" />
      </svg>
    );
  }
  return icon;
}

export function DesktopSidebar({
  activeId,
  onNavigate,
  inboxUnreadTotal,
  connected,
  authUsername,
  authEnabled,
  authLogout,
}) {
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const userMenuRef = useRef(null);
  const pendingWorks = usePendingWorksContextOptional();
  const pendingWorksCount = pendingWorks?.count || 0;
  const pendingInterviewCount = pendingWorks?.pendingInterviewCount || 0;
  const userInitials = (authUsername || "AD").slice(0, 2).toUpperCase();
  const displayName = authUsername || "Administrator";

  useEffect(() => {
    if (!userMenuOpen) return undefined;
    function onDoc(e) {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target)) {
        setUserMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [userMenuOpen]);

  return (
    <aside className="desktop-sidebar desktop-sidebar--sigma">
      <button
        type="button"
        className="desktop-sidebar__brand"
        onClick={() => onNavigate("dashboard")}
        aria-label="Go to dashboard"
      >
        <span className="desktop-sidebar__logo" aria-hidden>
          ⚡
        </span>
        <span className="desktop-sidebar__title">TeleAutomation</span>
      </button>
      <nav className="desktop-sidebar__nav" aria-label="Main">
        {NAV.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`desktop-sidebar__link${activeId === item.id ? " desktop-sidebar__link--active" : ""}`}
            onClick={() => {
              if (item.external) {
                window.open(item.external, "_blank", "noopener,noreferrer");
              } else {
                onNavigate(item.id);
              }
            }}
          >
            <span className="desktop-sidebar__link-icon" aria-hidden>
              <NavIcon icon={item.icon} />
            </span>
            {item.label}
            {item.badgeKey === "inbox" && inboxUnreadTotal > 0 && (
              <span className="desktop-sidebar__badge">
                {inboxUnreadTotal > 99 ? "99+" : inboxUnreadTotal}
              </span>
            )}
            {item.badgeKey === "pendingWorks" && pendingWorksCount > 0 && (
              <span className="desktop-sidebar__badge">
                {pendingWorksCount > 99 ? "99+" : pendingWorksCount}
              </span>
            )}
            {item.badgeKey === "pendingInterviews" &&
              pendingInterviewCount > 0 && (
                <span className="desktop-sidebar__badge">
                  {pendingInterviewCount > 99 ? "99+" : pendingInterviewCount}
                </span>
              )}
          </button>
        ))}
      </nav>
      <div className="desktop-sidebar__footer">
        <div className="desktop-sidebar__status">
          <span className="desktop-sidebar__status-check" aria-hidden>
            ✓
          </span>
          {connected ? "All systems operational" : "Reconnecting…"}
        </div>
        <div className="desktop-sidebar__uptime">
          <span>Uptime 99.98%</span>
          <div className="desktop-sidebar__uptime-bar" aria-hidden>
            <div
              className="desktop-sidebar__uptime-fill"
              style={{ width: "99.98%" }}
            />
          </div>
        </div>
        <div className="desktop-sidebar__version">Version v2.4.1</div>
        <div className="desktop-sidebar__user-wrap" ref={userMenuRef}>
          <button
            type="button"
            className="desktop-sidebar__user"
            aria-expanded={userMenuOpen}
            onClick={() => setUserMenuOpen((v) => !v)}
            title={displayName}
          >
            <span className="desktop-sidebar__user-avatar" aria-hidden>
              {userInitials}
            </span>
            <span className="desktop-sidebar__user-text">
              <span className="desktop-sidebar__user-name">{displayName}</span>
              <span className="desktop-sidebar__user-role">Administrator</span>
            </span>
            <span className="desktop-sidebar__user-chev" aria-hidden>
              ▾
            </span>
          </button>
          {userMenuOpen && (
            <div className="desk-user-menu desk-user-menu--sidebar" role="menu">
              {authEnabled ? (
                <button
                  type="button"
                  className="desk-user-menu__item desk-user-menu__item--danger"
                  role="menuitem"
                  onClick={() => {
                    setUserMenuOpen(false);
                    authLogout?.();
                  }}
                >
                  Sign out
                </button>
              ) : (
                <p className="desk-user-menu__hint">
                  Login not required on this server.
                </p>
              )}
              <button
                type="button"
                className="desk-user-menu__item"
                role="menuitem"
                onClick={() => {
                  setUserMenuOpen(false);
                  onNavigate("admin");
                }}
              >
                Admin
              </button>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
