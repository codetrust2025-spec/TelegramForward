import React from "react";
import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MailMonitoringNotifications, MailNotificationBell } from "./MailMonitoringNotifications.jsx";

class FakeWebSocket {
  static OPEN = 1;
  readyState = 1;
  constructor() { setTimeout(() => this.onopen?.(), 0); }
  send() {}
  close() { this.onclose?.(); }
}

const notification = {
  id: "notification-1", candidate_id: "candidate-1", candidate_name: "Rahul Kumar",
  candidate_email: "rahul@example.com", company_name: "Infosys", job_role: "Software Engineer",
  classification: "offer_received", candidate_status: "Offer Received", priority: "high",
  email_subject: "Formal employment offer", sender_name: "Recruiter", sender_email: "hr@infosys.example",
  ai_confidence: 0.94, ai_summary: "A formal offer was issued.", ai_reason: "Employment terms are confirmed.",
  recommended_action: "Verify the offer with the candidate.", is_read: false, is_reviewed: false,
  created_at: "2026-07-15T05:00:00Z",
};

function response(body) { return Promise.resolve({ ok: true, json: () => Promise.resolve(body) }); }

describe("mail monitoring notifications", () => {
  beforeEach(() => {
    vi.stubGlobal("WebSocket", FakeWebSocket);
    vi.stubGlobal("fetch", vi.fn((url) => {
      if (String(url).includes("/config")) return response({ enabled: true });
      if (String(url).includes("/summary")) return response({ summary: { unread: 1, new_offers: 1, selections: 0, joining_confirmations: 0, needs_review: 0 } });
      if (String(url).includes("/notifications")) return response({ notifications: [notification], total: 1 });
      return response({ status: "ok" });
    }));
  });
  afterEach(() => vi.unstubAllGlobals());

  it("shows the persisted unread count and latest notification", async () => {
    render(<MailNotificationBell />);
    await waitFor(() => expect(screen.getByLabelText("1 unread mail monitoring notifications")).toBeInTheDocument());
    fireEvent.click(screen.getByLabelText("1 unread mail monitoring notifications"));
    expect(await screen.findByText(/Rahul Kumar · Infosys/)).toBeInTheDocument();
    expect(screen.getByText("Offer Received")).toBeInTheDocument();
  });

  it("renders summary, filters, pagination and manual review actions", async () => {
    render(<MailMonitoringNotifications />);
    expect(await screen.findByRole("heading", { name: "Mail Monitoring Notifications" })).toBeInTheDocument();
    expect(await screen.findByText("Formal employment offer")).toBeInTheDocument();
    expect(screen.getByLabelText("Classification filter")).toBeInTheDocument();
    expect(screen.getByLabelText("Candidate status filter")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Open" }));
    expect(await screen.findByRole("button", { name: "Re-run AI" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start payment follow-up" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save correction" })).toBeInTheDocument();
  });
});

