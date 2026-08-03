/**
 * Responsive audit harness — development only, never part of the app build.
 *
 * Mounts a real panel with a mocked API so authenticated screens can be
 * measured in a real browser at real breakpoints, without production
 * credentials and without touching production data.
 *
 *   /harness/?panel=candidates&data=long
 */
import React from "react";
import { createRoot } from "react-dom/client";

import { installMockApi } from "./mockApi.js";

const params = new URLSearchParams(location.search);
installMockApi(params.get("data") || "normal");

// Styles exactly as the app loads them.
import "../src/teleautomation.css";
import "../src/index.css";
import "../src/responsive.css";

import { AuthProvider } from "../src/context/AuthContext.jsx";
import { ConfirmProvider } from "../src/context/ConfirmContext.jsx";
import { PendingWorksProvider } from "../src/dailyOps/PendingWorksProvider.jsx";
import { CandidatesPanel } from "../src/candidates/candidatesModule.jsx";
import { AdminPanel } from "../src/admin/adminModule.jsx";
import { DataRoomPanel } from "../src/components/DataRoomPanel.jsx";
import { KnowledgeAssistantPanel } from "../src/components/KnowledgeAssistantPanel.jsx";
import { DailyOpsPanel } from "../src/dailyOps/DailyOpsPanel.jsx";
import { InboxPanel } from "../src/components/InboxPanel.jsx";
import RecruitmentMailPanel from "../src/components/RecruitmentMailPanelRedesign.jsx";

const PANELS = {
  candidates: () => <CandidatesPanel />,
  admin: () => <AdminPanel />,
  data: () => <DataRoomPanel />,
  knowledge: () => <KnowledgeAssistantPanel />,
  "daily-ops": () => (
    <DailyOpsPanel loggedInSlots={[]} accountInfo={{}} onSelectAccount={() => {}} />
  ),
  inbox: () => (
    <InboxPanel
      inboxState={{ conversations: [], messages: {}, selected: null }}
      inboxLiveQueueRef={{ current: [] }}
      inboxLiveTick={0}
      onInboxPatch={() => {}}
      accountSlots={[]}
      crmState={{}}
      onCrmUpdate={() => {}}
      onBackToDashboard={() => {}}
    />
  ),
  recruitment: () => <RecruitmentMailPanel />,
};

function Harness() {
  const name = params.get("panel") || "candidates";
  // The app swaps shells at 768px; mirror that so each width is measured in
  // the wrapper the user actually gets.
  const mobile = window.innerWidth < 768;
  const render = PANELS[name];
  if (!render) {
    return (
      <pre style={{ color: "#eee", padding: 16 }}>
        unknown panel: {name}
        {"\n"}available: {Object.keys(PANELS).join(", ")}
      </pre>
    );
  }
  return (
    <AuthProvider>
      <ConfirmProvider>
        <PendingWorksProvider mainView={name}>
          {/* Reproduce the real content wrappers. Without them a panel is
              measured in a container the app never gives it, which reports
              widths that cannot happen in production. */}
          <div className="app-shell" data-harness-panel={name}>
            {mobile ? (
              <main className="mobile-app__main">{render()}</main>
            ) : (
              <div className="desktop-body">{render()}</div>
            )}
          </div>
        </PendingWorksProvider>
      </ConfirmProvider>
    </AuthProvider>
  );
}

const root = createRoot(document.getElementById("root"));
root.render(<Harness />);
window.__harnessReady = true;
