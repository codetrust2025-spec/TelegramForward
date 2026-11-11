import React, { useCallback, useEffect, useState } from "react";
import { Spinner } from "../Loader.jsx";
import { DesktopSidebar } from "./DesktopSidebar.jsx";
import { DesktopHeader } from "./DesktopHeader.jsx";
import { DesktopDashboardHome } from "./DesktopDashboardHome.jsx";
import { InboxPanel } from "../components/InboxPanel.jsx";
import { CandidatesPanel } from "../components/CandidatesPanel.jsx";
import { DataRoomPanel } from "../components/DataRoomPanel.jsx";
import { AdminPanel } from "../components/AdminPanel.jsx";
import { KnowledgeAssistantPanel } from "../components/KnowledgeAssistantPanel.jsx";
import { DailyBriefingCard } from "../components/DailyBriefingCard.jsx";
import { RecruitmentMailPanel } from "../components/RecruitmentMailPanel.jsx";
import { MailMonitoringNotifications } from "../components/MailMonitoringNotifications.jsx";
import AttendanceAdminPanel from "../attendance/AttendanceAdminPanel.jsx";
import { OutcomeAuditPanel } from "../components/OutcomeAuditPanel.jsx";
import PaymentReconciliationPanel from "../components/PaymentReconciliationPanel.jsx";
import BgvRegisterPanel from "../components/BgvRegisterPanel.jsx";
import { LogPanel } from "../components/LogPanel.jsx";
import { ProgressHubPanel } from "../components/ProgressHubPanel.jsx";
import { SetupMainPanel } from "../components/SetupMainPanel.jsx";
import { AccountPanel } from "../components/AccountPanel.jsx";
import { ForwarderConsole } from "./ForwarderConsole.jsx";
import { FleetDefaultsPanel } from "../components/FleetDefaultsPanel.jsx";
import { ShutdownListPanel } from "../components/ShutdownListPanel.jsx";
import { GroupsUpload } from "../components/GroupsUpload.jsx";
import { SetupAccountPicker } from "../components/SetupAccountPicker.jsx";
import { ResponsiveOptions } from "../components/ui/ResponsiveOptions.jsx";
import {
  WORKSPACE_CAMPAIGN,
  WORKSPACE_FLEET,
  WORKSPACE_FORWARDING,
} from "../utils/workspaceMode.js";
import { getDashboardModeFilter } from "../utils/workspaceDashboard.js";
import { API } from "../config.js";
import { statsResetConfirmOptions } from "../utils/statsResetConfirm.js";
import { accountRowsForDashboard } from "../dashboard/dashboardStats.js";
import { DailyOpsPanel } from "../dailyOps/DailyOpsPanel.jsx";
import "./desktopDashboard.css";

const THEME_STORAGE_KEY = "teleautomation-theme";

function initialTheme() {
  try {
    return window.localStorage.getItem(THEME_STORAGE_KEY) === "light"
      ? "light"
      : "dark";
  } catch {
    return "dark";
  }
}

function sidebarActiveId(mainView, desktopPage, workspaceMode) {
  if (mainView === "inbox") return "inbox";
  if (mainView === "logs") return "logs";
  if (mainView === "admin") return "admin";
  if (mainView === "candidates") return "candidates";
  if (mainView === "knowledge") return "knowledge";
  if (mainView === "daily-briefing") return "daily-briefing";
  if (mainView === "ai-recruitment") return "ai-recruitment";
  if (mainView === "mail-notifications") return "mail-notifications";
  if (mainView === "outcome-audit") return "outcome-audit";
  if (mainView === "payment-reconciliation") return "payment-reconciliation";
  if (mainView === "bgv-register") return "bgv-register";
  if (mainView === "attendance") return "attendance";
  if (mainView === "daily-ops") return "daily-ops";
  if (mainView === "data-room") return "data";
  if (desktopPage === "setup" || desktopPage === "login") return "accounts";
  if (desktopPage === "fleet") return "accounts";
  if (desktopPage === "shutdown") return "settings";
  if (desktopPage === "progress") return "dashboard";
  if (workspaceMode === WORKSPACE_CAMPAIGN) return "campaigns";
  if (workspaceMode === WORKSPACE_FORWARDING) return "forwarding";
  if (workspaceMode === WORKSPACE_FLEET) return "dashboard";
  return "dashboard";
}

export function DesktopApp({
  showBootOverlay,
  connected,
  mainView,
  setMainView,
  desktopPage,
  setDesktopPage,
  setWorkspaceMode,
  workspaceMode,
  unlockNotificationSound,
  fetchInbox,
  inboxUnreadTotal,
  inboxUnreadBadge,
  anyRunning,
  canStartMore,
  bulkActionLoading,
  onStartAll,
  onStopAll,
  totalListLoading,
  onTotalList,
  authUsername,
  authEnabled,
  authLogout,
  fleet,
  globalCountdown,
  sentWindowLabel,
  state,
  loggedInSlots,
  postingModes,
  switchAccount,
  overviewScope,
  onSelectAllAccounts,
  refreshAccounts,
  startAccount,
  stopAccount,
  accountActionLoading,
  shutdownListCount,
  setupLoggedInSlots,
  handleSetupAccountFilter,
  handleAccountModeApplied,
  subscriptionSlots,
  switchingAccount,
  setSetupTab,
  setupTab,
  setupTabOptions,
  modesProps,
  inboxProps,
  logsProps,
  progressHubProps,
  confirm,
  setupPanelProps,
  tickOverview,
  recentLogs,
  groupsUploadProps,
  groupsModal,
  incomingCallModal,
}) {
  const [theme, setTheme] = useState(initialTheme);
  const activeId = sidebarActiveId(mainView, desktopPage, workspaceMode);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, theme);
    } catch {
      // Theme still works when storage is disabled.
    }
  }, [theme]);

  const toggleTheme = useCallback(() => {
    setTheme((current) => (current === "dark" ? "light" : "dark"));
  }, []);

  const handleSidebar = useCallback(
    (id) => {
      unlockNotificationSound?.();
      switch (id) {
        case "dashboard":
          setWorkspaceMode(WORKSPACE_FLEET);
          onSelectAllAccounts?.();
          setMainView("dashboard");
          setDesktopPage("home");
          break;
        case "accounts":
          setMainView("dashboard");
          setDesktopPage("setup");
          setSetupTab?.("login");
          break;
        case "forwarding":
          setWorkspaceMode(WORKSPACE_FORWARDING);
          setMainView("dashboard");
          setDesktopPage("home");
          break;
        case "campaigns":
          setWorkspaceMode(WORKSPACE_CAMPAIGN);
          setMainView("dashboard");
          setDesktopPage("home");
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
        case "mail-notifications":
          setMainView("mail-notifications");
          break;
        case "outcome-audit":
          setMainView("outcome-audit");
          break;
        case "payment-reconciliation":
          setMainView("payment-reconciliation");
          break;
        case "bgv-register":
          setMainView("bgv-register");
          break;
        case "attendance":
          setMainView("attendance");
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
          setDesktopPage("shutdown");
          setSetupTab?.("shutdown");
          break;
        default:
          break;
      }
    },
    [
      setMainView,
      setDesktopPage,
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

  const modeFilter = getDashboardModeFilter(workspaceMode);
  const accounts = accountRowsForDashboard(
    state,
    loggedInSlots,
    postingModes,
    modeFilter,
  );
  const activeRow = accounts.find((a) => a.slot === state.active_account);
  const activeRunning = !!activeRow?.running;

  let bodyClass = "desktop-body";
  let content = null;

  if (mainView === "inbox") {
    bodyClass += " desktop-body--flush";
    content = (
      <InboxPanel
        {...inboxProps}
        onBackToDashboard={() => handleSidebar("dashboard")}
      />
    );
  } else if (mainView === "logs") {
    bodyClass += " desktop-body--flush";
    content = (
      <div className="logs-fullpage">
        <LogPanel {...logsProps} />
      </div>
    );
  } else if (mainView === "admin") {
    content = <AdminPanel />;
  } else if (mainView === "candidates") {
    content = <CandidatesPanel />;
  } else if (mainView === "knowledge") {
    content = <KnowledgeAssistantPanel />;
  } else if (mainView === "daily-briefing") {
    content = (
      <div className="daily-briefing-page">
        <DailyBriefingCard />
      </div>
    );
  } else if (mainView === "ai-recruitment") {
    content = <RecruitmentMailPanel />;
  } else if (mainView === "mail-notifications") {
    content = <MailMonitoringNotifications />;
  } else if (mainView === "outcome-audit") {
    content = <OutcomeAuditPanel />;
  } else if (mainView === "payment-reconciliation") {
    content = <PaymentReconciliationPanel />;
  } else if (mainView === "bgv-register") {
    content = <BgvRegisterPanel />;
  } else if (mainView === "attendance") {
    content = <AttendanceAdminPanel />;
  } else if (mainView === "daily-ops") {
    bodyClass += " desktop-body--daily-ops";
    content = (
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
  } else if (mainView === "data-room") {
    content = <DataRoomPanel />;
  } else if (desktopPage === "progress") {
    content = <ProgressHubPanel {...progressHubProps} />;
  } else if (desktopPage === "shutdown") {
    content = (
      <div className="desk-setup-wrap">
        <ShutdownListPanel
          shutdownList={state.shutdown_list}
          accountShutdown={state.account_shutdown}
          accountInfo={state.account_info}
          onUpdated={refreshAccounts}
          embedInTab
        />
      </div>
    );
  } else if (desktopPage === "setup") {
    content = (
      <ForwarderConsole
        state={state}
        workspaceMode={workspaceMode}
        loggedInSlots={loggedInSlots}
        setupLoggedInSlots={setupLoggedInSlots}
        postingModes={postingModes}
        subscriptionSlots={subscriptionSlots}
        switchingAccount={switchingAccount}
        switchAccount={switchAccount}
        refreshAccounts={refreshAccounts}
        handleSetupAccountFilter={handleSetupAccountFilter}
        handleAccountModeApplied={handleAccountModeApplied}
        modesProps={modesProps}
        setupPanelProps={setupPanelProps}
        groupsUploadProps={groupsUploadProps}
        shutdownListCount={shutdownListCount}
        totalListLoading={totalListLoading}
        onTotalList={onTotalList}
        onSetSetupTab={setSetupTab}
      />
    );
  } else {
    content = (
      <DesktopDashboardHome
        state={state}
        loggedInSlots={loggedInSlots}
        postingModes={postingModes}
        inboxUnreadTotal={inboxUnreadTotal}
        fleet={fleet}
        globalCountdown={globalCountdown}
        sentWindowLabel={sentWindowLabel}
        activeSlot={state.active_account}
        activeRunning={activeRunning}
        anyProcessRunning={anyRunning}
        onSelectAccount={switchAccount}
        onOpenSetup={() => {
          setDesktopPage("setup");
          setSetupTab?.("setup");
        }}
        onOpenProgress={() => setDesktopPage("progress")}
        onResetReach={handleResetReach}
        onStartAccount={startAccount}
        onStopAccount={stopAccount}
        accountActionLoading={accountActionLoading}
        shutdownListCount={shutdownListCount}
        onNavBulk={() => {
          setDesktopPage("setup");
          setSetupTab?.(
            workspaceMode === WORKSPACE_CAMPAIGN ? "setup" : "fleet",
          );
        }}
        onNavShutdown={() => {
          setDesktopPage("shutdown");
          setSetupTab?.("shutdown");
        }}
        onNavLogs={() => setMainView("logs")}
        onNavData={() => setMainView("data-room")}
        onNavCandidates={() => setMainView("candidates")}
        tickOverview={tickOverview}
        recentLogs={recentLogs}
        workspaceMode={workspaceMode}
      />
    );
  }

  return (
    <>
      <div className="desktop-app">
        {showBootOverlay && (
          <div className="app-boot-overlay" role="status" aria-live="polite">
            <Spinner size={32} />
            <span className="overlay-loader-label">Connecting…</span>
          </div>
        )}

        <DesktopSidebar
          activeId={activeId}
          onNavigate={handleSidebar}
          inboxUnreadTotal={inboxUnreadTotal}
          connected={connected}
          authUsername={authUsername}
          authEnabled={authEnabled}
          authLogout={authLogout}
        />

        <div className="desktop-main">
          <DesktopHeader
            activeAccount={state.active_account}
            accountInfo={state.account_info}
            loggedInSlots={loggedInSlots}
            postingModes={postingModes}
            state={state}
            workspaceMode={workspaceMode}
            overviewScope={overviewScope}
            fleet={fleet}
            activeRunning={activeRunning}
            anyRunning={anyRunning}
            canStartMore={canStartMore}
            bulkActionLoading={bulkActionLoading}
            onStartAll={onStartAll}
            onStopAll={onStopAll}
            totalListLoading={totalListLoading}
            onTotalList={onTotalList}
            onSelectAccount={switchAccount}
            onSelectAllAccounts={onSelectAllAccounts}
            inboxUnreadTotal={inboxUnreadTotal}
            inboxUnreadBadge={inboxUnreadBadge}
            onOpenInbox={() => handleSidebar("inbox")}
            authUsername={authUsername}
            authEnabled={authEnabled}
            authLogout={authLogout}
            connected={connected}
            theme={theme}
            onToggleTheme={toggleTheme}
          />
          <div className={bodyClass}>{content}</div>
        </div>
      </div>
      {groupsModal}
      {incomingCallModal}
    </>
  );
}
