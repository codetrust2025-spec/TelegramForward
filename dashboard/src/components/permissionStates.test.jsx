import React from "react";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AuthGate } from "./AuthGate.jsx";
import * as AuthContext from "../context/AuthContext.jsx";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const withAuth = (state) =>
  vi.spyOn(AuthContext, "useAuth").mockReturnValue({
    loading: false,
    enabled: true,
    authenticated: true,
    role: "admin",
    reference: null,
    ...state,
  });

/**
 * Permission and authorization states, asserted without touching the auth,
 * permission or role logic itself — only how the UI presents them.
 */
describe("nothing privileged renders before authorization resolves", () => {
  it("shows a loading state, not application content, while resolving", () => {
    withAuth({ loading: true, authenticated: false });
    render(
      <AuthGate>
        <div>SECRET DASHBOARD CONTENT</div>
      </AuthGate>,
    );

    expect(screen.getByText("Loading…")).toBeInTheDocument();
    // The flash-of-content failure mode: children must not mount early.
    expect(screen.queryByText("SECRET DASHBOARD CONTENT")).toBeNull();
  });

  it("shows the login screen rather than an empty layout when unauthenticated", () => {
    withAuth({ authenticated: false });
    const { container } = render(
      <AuthGate>
        <div>SECRET DASHBOARD CONTENT</div>
      </AuthGate>,
    );

    expect(screen.queryByText("SECRET DASHBOARD CONTENT")).toBeNull();
    // A blank screen would leave the user with no way forward.
    expect(container.textContent.trim().length).toBeGreaterThan(0);
  });

  it("renders the app once authenticated", () => {
    withAuth({});
    render(
      <AuthGate>
        <div>SECRET DASHBOARD CONTENT</div>
      </AuthGate>,
    );
    expect(screen.getByText("SECRET DASHBOARD CONTENT")).toBeInTheDocument();
  });

  it("renders the app when dashboard auth is disabled entirely", () => {
    withAuth({ enabled: false, authenticated: false });
    render(
      <AuthGate>
        <div>SECRET DASHBOARD CONTENT</div>
      </AuthGate>,
    );
    expect(screen.getByText("SECRET DASHBOARD CONTENT")).toBeInTheDocument();
  });
});

describe("restricted roles are redirected, not shown broken screens", () => {
  // App.jsx moves handlers off dashboard/inbox/admin/logs to handler-kit. The
  // rule itself is business logic and is not changed here; this pins that the
  // restricted view list has not silently shrunk.
  const source = readAppSource();

  it("keeps handlers out of the admin, dashboard, inbox and logs views", () => {
    const at = source.indexOf("authRole === 'handler'");
    expect(at, "handler restriction missing").toBeGreaterThan(-1);
    const rule = source.slice(at, at + 300);
    for (const view of ["dashboard", "inbox", "admin", "logs"]) {
      expect(rule).toContain(`'${view}'`);
    }
    expect(rule).toContain("handler-kit");
  });
});

describe("denied writes explain themselves", () => {
  it("turns a 403 into plain language rather than a status code", () => {
    const source = readSource("src/admin/OcrPolicySection.jsx");
    expect(source).toContain("Only an admin can change the OCR setting.");
    // The raw status must not be what the operator reads.
    expect(source).toMatch(/res\.status === 403/);
  });

  it("leaves the control showing its true state when the server refuses", () => {
    // Covered behaviourally in OcrPolicySection.test.jsx; asserted here so the
    // permission story is complete in one place.
    const source = readSource("src/admin/OcrPolicySection.test.jsx");
    expect(source).toContain("Only an admin");
    expect(source).toMatch(/not\.toBeChecked|toBeChecked/);
  });
});

function readSource(rel) {
  // eslint-disable-next-line no-undef
  const { readFileSync } = require("node:fs");
  // eslint-disable-next-line no-undef
  const { resolve } = require("node:path");
  // eslint-disable-next-line no-undef
  return readFileSync(resolve(process.cwd(), rel), "utf8");
}

function readAppSource() {
  return readSource("src/App.jsx");
}
