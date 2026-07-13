import React, { useState, useCallback } from "react";
import { Spinner } from "../Loader.jsx";
import { InboxPanel } from "../components/InboxPanel.jsx";
import { CandidatesPanel } from "../components/CandidatesPanel.jsx";
import { DataRoomPanel } from "../components/DataRoomPanel.jsx";
import { AdminPanel } from "../components/AdminPanel.jsx";
import { KnowledgeAssistantPanel } from "../components/KnowledgeAssistantPanel.jsx";
import { DailyBriefingCard } from "../components/DailyBriefingCard.jsx";
import { RecruitmentMailPanel } from "../components/RecruitmentMailPanel.jsx";
import {
  LogPanel,
  LogsToolbarTabs,
  LogToolbarActions,
} from "../components/LogPanel.jsx";
import { ProgressHubPanel } from "../components/ProgressHubPanel.jsx";
import { SetupMainPanel } from "../components/SetupMainPanel.jsx";
import { ShutdownListPanel } from "../components/ShutdownListPanel.jsx";
import { FleetDefaultsPanel } from "../components/FleetDefaultsPanel.jsx";
import { ResponsiveOptions } from "../components/ui/ResponsiveOptions.jsx";
import { MobileDashboardHome } from "./MobileDashboardHome.jsx";
import { DailyOpsPanel } from "../dailyOps/DailyOpsPanel.jsx";
import { API } from "../config.js";
import { formatLogTime } from "../utils/accountUi.js";
import { statsResetConfirmOptions } from "../utils/statsResetConfirm.js";
import {
  WORKSPACE_CAMPAIGN,
  WORKSPACE_FLEET,
  WORKSPACE_FORWARDING,
} from "../utils/workspaceMode.js";
import "./mobileDashboard.css";

const NAV_ITEMS = [
  { id: "home", label: "Dashboard", icon: "🏠" },
  { id: "inbox", label: "Inbox", icon: "✉" },
  { id: "accounts", label: "Accounts", icon: "👥" },
  { id: "logs", label: "Logs", icon: "📋" },
  { id: "admin", label: "Admin", icon: "⚙" },
];

const MORE_NAV_ITEMS = [
  { id: "knowledge", label: "Ask AI", icon: "AI" },
  { id: "daily-briefing", label: "Daily briefing", icon: "☀" },
  { id: "ai-recruitment", label: "AI Mail Review", icon: "AI" },
  { id: "dashboard", label: "Dashboard", icon: "▣" },
  { id: "accounts", label: "Accounts", icon: "👤" },
  { id: "forwarding", label: "Forwarding", icon: "↻" },
  { id: "campaigns", label: "Campaigns", icon: "📣" },
  { id: "inbox", label: "Inbox", icon: "✉" },
  { id: "candidates", label: "Candidates", icon: "📇" },
  { id: "daily-ops", label: "Daily ops", icon: "📅" },
  { id: "data", label: "Data", icon: "📊" },
  { id: "logs", label: "Logs", icon: "📋" },
  { id: "admin", label: "Admin", icon: "⚙" },
  { id: "settings", label: "Settings", icon: "⚙" },
];

function navToMainView(tab) {
  if (tab === "home" || tab === "accounts") return "dashboard";
  if (tab === "inbox") return "inbox";
  if (tab === "logs") return "logs";
  if (tab === "admin") return "admin";
  return "dashboard";
}

function mainViewToNav(mainView, mobilePage) {
  if (mainView === "inbox") return "inbox";
  if (mainView === "logs") return "logs";
  if (mainView === "admin") return "admin";
  if (
    mainView === "candidates" ||
    mainView === "knowledge" ||
    mainView === "daily-briefing" ||
    mainView === "ai-recruitment" ||
    mainView === "daily-ops" ||
    mainView === "data-room"
  ) {
    return "home";
  }
  if (
    mobilePage === "setup" ||
    mobilePage === "progress" ||
    mobilePage === "shutdown"
  )
    return "accounts";
  return "home";
}

export function MobileApp({
  showBootOverlay,
  connected,
  mainView,
  setMainView,
  mobilePage,
  setMobilePage,
  unlockNotificationSound,
  fetchInbox,
  inboxUnreadTotal,
  inboxUnreadBadge,
  connectedForHeader,
  anyRunning,
  workspaceAnyRunning,
  canStartMore,
  bulkActionLoading,
  onStartAll,
  onStopAll,
  hardRefreshing,
  onHardRefresh,
  totalListLoading,
  onTotalList,
  authEnabled,
  authUsername,
  authLogout,
  fleet,
  globalCountdown,
  sentWindowLabel,
  state,
  loggedInSlots,
  postingModes,
  workspaceMode,
  setWorkspaceMode,
  switchAccount,
  overviewScope,
  onSelectAllAccounts,
  refreshAccounts,
  startAccount,
  stopAccount,
  accountActionLoading,
  setupLoggedInSlots,
  handleSetupAccountFilter,
  handleAccountModeApplied,
  subscriptionSlots,
  switchingAccount,
  setSetupTab,
  setupTab,
  setupTabOptions,
  shutdownListCount,
  modesProps,
  inboxProps,
  logsProps,
  progressHubProps,
  confirm,
  onNavigateExtra,
  groupsModal,
  incomingCallModal,
}) {
  const [menuOpen, setMenuOpen] = useState(false);

  const activeNav = mainViewToNav(mainView, mobilePage);

  const handleNav = useCallback(
    (tab) => {
      unlockNotificationSound?.();
      const view = navToMainView(tab);
      setMainView(view);
      if (tab === "inbox") fetchInbox?.();
      if (tab === "home") setMobilePage("home");
      if (tab === "accounts") setMobilePage("setup");
      else if (view === "dashboard" && tab === "home") setMobilePage("home");
    },
    [setMainView, setMobilePage, fetchInbox, unlockNotificationSound],
  );

  const handleMoreNav = useCallback(
    (id) => {
      unlockNotificationSound?.();
      setMenuOpen(false);
      switch (id) {
        case "dashboard":
          setWorkspaceMode(WORKSPACE_FLEET);
          onSelectAllAccounts?.();
          setMainView("dashboard");
          setMobilePage("home");
          break;
        case "accounts":
          setMainView("dashboard");
          setMobilePage("setup");
          setSetupTab?.("login");
          break;
        case "forwarding":
          setWorkspaceMode(WORKSPACE_FORWARDING);
          setMainView("dashboard");
          setMobilePage("home");
          break;
        case "campaigns":
          setWorkspaceMode(WORKSPACE_CAMPAIGN);
          setMainView("dashboard");
          setMobilePage("home");
          break;
        case "inbox":
          setMainView("inbox");
          fetchInbox?.();
          break;
        case "candidates":
          setMainView("candidates");
          break;
        case "knowledge":
          setMainView("knowledge");
          break;
        case "daily-briefing":
          setMainView("daily-briefing");
          break;
        case "ai-recruitment":
          setMainView("ai-recruitment");
          break;
        case "daily-ops":
          setMainView("daily-ops");
          break;
        case "data":
          setMainView("data-room");
          break;
        case "logs":
          setMainView("logs");
          break;
        case "admin":
          setMainView("admin");
          break;
        case "settings":
          setMainView("dashboard");
          setMobilePage("shutdown");
          setSetupTab?.("shutdown");
          break;
        default:
          break;
      }
    },
    [
      setMainView,
      setMobilePage,
      setWorkspaceMode,
      onSelectAllAccounts,
      setSetupTab,
      fetchInbox,
      unlockNotificationSound,
    ],
  );

  async function handleResetReach() {
    const ok = await confirm?.(
      statsResetConfirmOptions({
        scope: "global",
        accountLabel: "All accounts",
      }),
    );
    if (!ok) return;
    try {
      const res = await fetch(`${API}/stats/reset`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ scope: "global" }),
      });
      const data = await res.json();
      if (data.status === "error") alert(data.message || "Reset failed");
      else refreshAccounts?.();
    } catch (e) {
      alert(e.message || "Reset failed");
    }
  }

  let mainContent = null;
  const mainClass = ["mobile-app__main"];

  if (mainView === "inbox") {
    mainClass.push("mobile-app__main--flush");
    mainContent = (
      <InboxPanel {...inboxProps} onBackToDashboard={() => handleNav("home")} />
    );
  } else if (mainView === "logs") {
    mainClass.push("mobile-app__main--flush");
    mainContent = (
      <div className="logs-fullpage">
        <LogPanel {...logsProps} />
      </div>
    );
  } else if (mainView === "admin") {
    mainContent = <AdminPanel />;
  } else if (mainView === "candidates") {
    mainContent = <CandidatesPanel />;
  } else if (mainView === "knowledge") {
    mainContent = <KnowledgeAssistantPanel />;
  } else if (mainView === "daily-briefing") {
    mainContent = (
      <div className="daily-briefing-page">
        <DailyBriefingCard />
      </div>
    );
  } else if (mainView === "ai-recruitment") {
    mainContent = <RecruitmentMailPanel />;
  } else if (mainView === "data-room") {
    mainContent = <DataRoomPanel />;
  } else if (mainView === "daily-ops") {
    mainClass.push("mobile-app__main--daily-ops");
    mainContent = (
      <DailyOpsPanel
        loggedInSlots={loggedInSlots}
        activeAccount={state.active_account}
        accountInfo={state.account_info}
        onSelectAccount={switchAccount}
        onStartAll={onStartAll}
        startAllBusy={bulkActionLoading === "start"}
        showFleetControls
        onNavCandidates={() => setMainView("candidates")}
      />
    );
  } else if (mobilePage === "progress") {
    mainContent = (
      <div className="mob-setup-wrap">
        <button
          type="button"
          className="mob-section-head__link"
          style={{ marginBottom: 8 }}
          onClick={() => setMobilePage("home")}
        >
          ‹ Back
        </button>
        <ProgressHubPanel {...progressHubProps} />
      </div>
    );
  } else if (mobilePage === "shutdown") {
    mainContent = (
      <div className="mob-setup-wrap">
        <button
          type="button"
          className="mob-section-head__link"
          style={{ marginBottom: 8 }}
          onClick={() => setMobilePage("home")}
        >
          ‹ Back to dashboard
        </button>
        <ShutdownListPanel
          shutdownList={state.shutdown_list}
          accountShutdown={state.account_shutdown}
          accountInfo={state.account_info}
          onUpdated={refreshAccounts}
          embedInTab
        />
      </div>
    );
  } else if (mobilePage === "setup") {
    mainContent = (
      <div className="mob-setup-wrap">
        <button
          type="button"
          className="mob-section-head__link"
          style={{ marginBottom: 8 }}
          onClick={() => setMobilePage("home")}
        >
          ‹ Back to dashboard
        </button>
        {setupTabOptions?.length > 1 && (
          <ResponsiveOptions
            className="setup-column-nav__tabs-wrap"
            segmentedClassName="setup-column-nav__tabs setup-column-tabs"
            label="Setup"
            options={setupTabOptions}
            value={setupTab}
            onChange={setSetupTab}
            role="tablist"
            compactColumns={2}
          />
        )}
        {setupTab === "fleet" ? (
          <FleetDefaultsPanel
            embedInTab
            workspaceMode={workspaceMode}
            loggedInCount={setupLoggedInSlots.length}
            onUpdated={refreshAccounts}
          />
        ) : setupTab === "shutdown" ? (
          <ShutdownListPanel
            shutdownList={state.shutdown_list}
            accountShutdown={state.account_shutdown}
            accountInfo={state.account_info}
            onUpdated={refreshAccounts}
            embedInTab
          />
        ) : (
          <SetupMainPanel
            slots={setupLoggedInSlots}
            accountFilter={workspaceMode}
            onAccountFilterChange={handleSetupAccountFilter}
            onModeApplied={handleAccountModeApplied}
            activeSlot={state.active_account}
            accountInfo={state.account_info}
            accountStates={state.account_states}
            postingModes={postingModes}
            accountShutdown={state.account_shutdown}
            subscriptionSlots={subscriptionSlots}
            switchingAccount={switchingAccount}
            onSelectAccount={switchAccount}
            onOpenLoginTab={() => setSetupTab?.("login")}
            onPostingModeUpdated={refreshAccounts}
            modesProps={modesProps}
          />
        )}
      </div>
    );
  } else {
    mainContent = (
      <MobileDashboardHome
        state={state}
        loggedInSlots={loggedInSlots}
        postingModes={postingModes}
        workspaceMode={workspaceMode}
        onWorkspaceModeChange={setWorkspaceMode}
        anyProcessRunning={anyRunning}
        inboxUnreadTotal={inboxUnreadTotal}
        fleet={fleet}
        globalCountdown={globalCountdown}
        sentWindowLabel={sentWindowLabel}
        activeSlot={state.active_account}
        overviewScope={overviewScope}
        onSelectAccount={switchAccount}
        onSelectAllAccounts={onSelectAllAccounts}
        onRefreshAccounts={refreshAccounts}
        onStartAll={onStartAll}
        onStopAll={onStopAll}
        onStartAccount={startAccount}
        onStopAccount={stopAccount}
        canStartMore={canStartMore}
        anyRunning={anyRunning}
        bulkActionLoading={bulkActionLoading}
        accountActionLoading={accountActionLoading}
        shutdownListCount={shutdownListCount}
        onOpenSetup={() => {
          setMobilePage("setup");
          setSetupTab?.("setup");
        }}
        onOpenProgress={() => setMobilePage("progress")}
        onResetReach={handleResetReach}
        onNavBulk={() => {
          setMobilePage("setup");
          setSetupTab?.("fleet");
        }}
        onNavShutdown={() => setMobilePage("shutdown")}
        onNavLogs={() => handleNav("logs")}
      />
    );
  }

  return (
    <>
      <div className="mobile-app">
        {showBootOverlay && (
          <div className="app-boot-overlay" role="status" aria-live="polite">
            <Spinner size={32} />
            <span className="overlay-loader-label">Connecting…</span>
          </div>
        )}

        <header className="mobile-header">
          <button
            type="button"
            className="mobile-header__menu"
            aria-label="Menu"
            onClick={() => setMenuOpen(true)}
          >
            ☰
          </button>
          <button
            type="button"
            className="mobile-header__brand"
            onClick={() => {
              setMenuOpen(false);
              handleNav("home");
            }}
            aria-label="Go to dashboard"
          >
            <span className="mobile-header__bolt" aria-hidden>
              ⚡
            </span>
            TeleAutomation
          </button>
          <div className="mobile-header__actions">
            {anyRunning && (
              <span
                className="mobile-header__status-pill"
                title="Accounts running"
              >
                <span className="mobile-header__status-dot" aria-hidden />
                Running
              </span>
            )}
            {!connectedForHeader && (
              <span className="mobile-header__status-pill mobile-header__status-pill--off">
                Offline
              </span>
            )}
            {!anyRunning ? (
              <button
                type="button"
                className="mobile-header__bulk mobile-header__bulk--start"
                disabled={!canStartMore || !!bulkActionLoading}
                onClick={onStartAll}
              >
                ▶ Start all
              </button>
            ) : (
              <button
                type="button"
                className="mobile-header__bulk mobile-header__bulk--stop"
                disabled={!!bulkActionLoading}
                onClick={onStopAll}
              >
                ■ Stop all
              </button>
            )}
            {onTotalList && (
              <button
                type="button"
                className="mobile-header__bell mobile-header__util-btn"
                onClick={onTotalList}
                disabled={totalListLoading}
                title="Download joined groups CSV for all accounts"
                aria-label="Total list CSV"
              >
                <span aria-hidden>{totalListLoading ? "…" : "📋"}</span>
              </button>
            )}
            <button
              type="button"
              className="mobile-header__bell"
              aria-label={`${inboxUnreadTotal} inbox notifications`}
              onClick={() => handleNav("inbox")}
            >
              🔔
              {inboxUnreadTotal > 0 && (
                <span className="mobile-header__bell-badge">
                  {inboxUnreadBadge}
                </span>
              )}
            </button>
          </div>
        </header>

        <main className={mainClass.join(" ")}>{mainContent}</main>

        <nav className="mobile-bottom-nav" aria-label="Main">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`mobile-bottom-nav__btn${activeNav === item.id ? " mobile-bottom-nav__btn--active" : ""}`}
              onClick={() => handleNav(item.id)}
            >
              <span className="mobile-bottom-nav__icon-wrap">
                <span className="mobile-bottom-nav__icon" aria-hidden>
                  {item.icon}
                </span>
                {item.id === "inbox" && inboxUnreadTotal > 0 && (
                  <span className="mobile-bottom-nav__badge">
                    {inboxUnreadBadge}
                  </span>
                )}
              </span>
              {item.label}
            </button>
          ))}
        </nav>

        <div
          className={`mobile-drawer${menuOpen ? " mobile-drawer--open" : ""}`}
        >
          <div
            className="mobile-drawer__backdrop"
            role="presentation"
            onClick={() => setMenuOpen(false)}
          />
          <div className="mobile-drawer__panel" role="dialog" aria-label="Menu">
            <p className="mob-section-title">More</p>
            {authEnabled && (
              <p className="mob-account-card__sub" style={{ marginBottom: 8 }}>
                Signed in as {authUsername || "operator"}
              </p>
            )}
            {MORE_NAV_ITEMS.map((item) => (
              <button
                key={item.id}
                type="button"
                className="mobile-drawer__item"
                onClick={() => handleMoreNav(item.id)}
              >
                <span className="mobile-drawer__item-icon" aria-hidden>
                  {item.icon}
                </span>
                {item.label}
              </button>
            ))}
            <button
              type="button"
              className="mobile-drawer__item mobile-drawer__item--secondary"
              onClick={() => {
                setMenuOpen(false);
                setMobilePage("setup");
                setMainView("dashboard");
                setSetupTab?.("setup");
              }}
            >
              Full setup
            </button>
            {anyRunning && (
              <button
                type="button"
                className="mobile-drawer__item"
                disabled={!!bulkActionLoading}
                onClick={() => {
                  setMenuOpen(false);
                  onStopAll?.();
                }}
              >
                ⏹ Stop all accounts
              </button>
            )}
            <button
              type="button"
              className="mobile-drawer__item"
              onClick={() => {
                setMenuOpen(false);
                onHardRefresh?.();
              }}
            >
              {hardRefreshing ? "Refreshing…" : "Hard refresh"}
            </button>
            {authEnabled && (
              <button
                type="button"
                className="mobile-drawer__item"
                onClick={() => {
                  setMenuOpen(false);
                  authLogout?.();
                }}
              >
                Sign out
              </button>
            )}
          </div>
        </div>
      </div>
      {groupsModal}
      {incomingCallModal}
    </>
  );
}
