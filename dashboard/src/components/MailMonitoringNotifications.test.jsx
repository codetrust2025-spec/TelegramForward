import React from "react";
import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MailMonitoringNotifications, MailNotificationBell, mailStatusTone } from "./MailMonitoringNotifications.jsx";
import { ConfirmProvider } from "../context/ConfirmContext.jsx";

class FakeWebSocket {
  static OPEN = 1;
  readyState = 1;
  constructor() { setTimeout(() => this.onopen?.(), 0); }
  send() {}
  close() { this.onclose?.(); }
}

const notification = {
  id: "notification-1", candidate_id: "candidate-1", candidate_name: "Rahul Kumar",
  ai_recruitment_event_id: "event-1", gmail_message_id: "gmail-message-1",
  candidate_email: "rahul@example.com", company_name: "Infosys", job_role: "Software Engineer",
  classification: "offer_received", candidate_status: "Offer Received", priority: "high",
  email_subject: "Formal employment offer", sender_name: "Recruiter", sender_email: "hr@infosys.example",
  ai_confidence: 0.94, ai_summary: "A formal offer was issued.", ai_reason: "Employment terms are confirmed.",
  recommended_action: "Verify the offer with the candidate.", is_read: false, is_reviewed: false,
  email_received_at: "2026-07-15T04:55:00Z",
  created_at: "2026-07-15T05:00:00Z",
  interview_date: "2026-07-23", interview_time: "17:30", interview_timezone: "Asia/Kolkata",
};

function response(body) { return Promise.resolve({ ok: true, json: () => Promise.resolve(body) }); }
function renderNotifications() {
  return render(<ConfirmProvider><MailMonitoringNotifications /></ConfirmProvider>);
}

describe("mail monitoring notifications", () => {
  it("uses semantic colors for booking outcomes", () => {
    expect(mailStatusTone({ candidate_status: "Interview Automatically Booked" })).toBe("success");
    expect(mailStatusTone({ candidate_status: "Automatic Booking Blocked" })).toBe("warning");
    expect(mailStatusTone({ booking_status: "Processing Failed" })).toBe("danger");
    expect(mailStatusTone({ candidate_status: "Needs Review" })).toBe("review");
    expect(mailStatusTone({ candidate_status: "Already Booked — Duplicate Ignored" })).toBe("success");
    expect(mailStatusTone({ candidate_status: "Historical Interview — Review Only" })).toBe("review");
    expect(mailStatusTone({ candidate_status: "Historical Interview Skipped" })).toBe("neutral");
  });

  beforeEach(() => {
    vi.stubGlobal("WebSocket", FakeWebSocket);
    vi.stubGlobal("fetch", vi.fn((url) => {
      if (String(url).includes("/config")) return response({ enabled: true });
      if (String(url).includes("/summary")) return response({ summary: { unread: 1, new_offers: 1, selections: 0, joining_confirmations: 0, needs_review: 0 } });
      if (String(url).includes("/api/ai-recruitment/events/event-1")) return response({
        event: {
          received_email: {
            subject: "Formal employment offer",
            sender_name: "Recruiter",
            sender_email: "hr@infosys.example",
            recipient_email: "rahul@example.com",
            sent_at: "2026-07-15T04:55:00Z",
            body: "Dear Rahul,\nWe are pleased to offer you the role.",
          },
        },
      });
      if (String(url).includes("/notifications")) return response({ notifications: [notification], total: 1 });
      return response({ status: "ok" });
    }));
  });
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("shows the persisted unread count and latest notification", async () => {
    render(<MailNotificationBell />);
    await waitFor(() => expect(screen.getByLabelText("1 unread mail monitoring notifications")).toBeInTheDocument());
    fireEvent.click(screen.getByLabelText("1 unread mail monitoring notifications"));
    expect(await screen.findByText(/Rahul Kumar · Infosys/)).toBeInTheDocument();
    expect(screen.getByText("Offer Received")).toBeInTheDocument();
  });

  it("renders summary, filters, pagination and manual review actions", async () => {
    renderNotifications();
    expect(await screen.findByRole("heading", { name: "Mail Monitoring Notifications" })).toBeInTheDocument();
    expect(await screen.findByText("Formal employment offer")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Mail received" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Tool detected" })).toBeInTheDocument();
    expect(screen.getByLabelText("Classification filter")).toBeInTheDocument();
    expect(screen.queryByLabelText("Candidate status filter")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Priority filter")).not.toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Open email notification: Formal employment offer"));
    expect(await screen.findByText(/We are pleased to offer you the role/)).toBeInTheDocument();
    await waitFor(() => expect(fetch).toHaveBeenCalledWith(
      "/api/mail-monitoring/notifications/notification-1/read",
      expect.objectContaining({ method: "POST" }),
    ));
    expect(await screen.findByText("23 Jul 2026, 5:30 pm IST")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Re-run AI" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start payment follow-up" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save correction" })).toBeInTheDocument();
  });

  it("clears the complete notification list after confirmation", async () => {
    renderNotifications();
    const button = await screen.findByRole("button", { name: "Clear all notifications" });
    fireEvent.click(button);
    expect(await screen.findByText("Clear all mail notifications?")).toBeInTheDocument();
    expect(screen.getByText("Email evidence")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Clear notifications"));
    await waitFor(() => expect(fetch).toHaveBeenCalledWith(
      "/api/mail-monitoring/notifications/clear-all",
      expect.objectContaining({ method: "POST" }),
    ));
  });
});
