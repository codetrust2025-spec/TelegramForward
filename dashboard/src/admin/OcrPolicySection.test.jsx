import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

import { OcrPolicySection } from "./OcrPolicySection.jsx";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function jsonResponse(body, { ok = true, status = 200 } = {}) {
  return Promise.resolve({
    ok,
    status,
    headers: { get: () => "application/json" },
    json: () => Promise.resolve(body),
  });
}

const ON = { enabled: true, mode: "ocr+ai", source: "admin", updated_by: "alice" };
const OFF = { enabled: false, mode: "ai", source: "admin", updated_by: "alice" };

describe("OcrPolicySection", () => {
  it("shows the current mode as OCR + AI when OCR is on", async () => {
    vi.stubGlobal("fetch", vi.fn(() => jsonResponse(ON)));
    render(<OcrPolicySection apiBase="/api" />);
    expect(await screen.findByText("OCR + AI")).toBeInTheDocument();
    expect(screen.getByRole("checkbox")).toBeChecked();
  });

  it("shows AI only when OCR is off", async () => {
    vi.stubGlobal("fetch", vi.fn(() => jsonResponse(OFF)));
    render(<OcrPolicySection apiBase="/api" />);
    expect(await screen.findByText("AI only")).toBeInTheDocument();
    expect(screen.getByRole("checkbox")).not.toBeChecked();
  });

  it("confirms before turning OCR off and warns about the project-wide effect", async () => {
    const confirmSpy = vi.fn(() => false);
    vi.stubGlobal("confirm", confirmSpy);
    const fetchSpy = vi.fn(() => jsonResponse(ON));
    vi.stubGlobal("fetch", fetchSpy);

    render(<OcrPolicySection apiBase="/api" />);
    await screen.findByText("OCR + AI");
    fireEvent.click(screen.getByRole("checkbox"));

    expect(confirmSpy).toHaveBeenCalledTimes(1);
    expect(confirmSpy.mock.calls[0][0]).toMatch(/whole project/i);
    // Declining must not send anything.
    expect(fetchSpy.mock.calls.filter(([, init]) => init?.method === "PUT")).toHaveLength(0);
  });

  it("persists the change and reports success", async () => {
    vi.stubGlobal("confirm", () => true);
    const fetchSpy = vi.fn((url, init) =>
      init?.method === "PUT" ? jsonResponse(OFF) : jsonResponse(ON),
    );
    vi.stubGlobal("fetch", fetchSpy);

    render(<OcrPolicySection apiBase="/api" />);
    await screen.findByText("OCR + AI");
    fireEvent.click(screen.getByRole("checkbox"));

    await waitFor(() => expect(screen.getByRole("status").textContent).toMatch(/OCR is now OFF/i));
    expect(screen.getByText("AI only")).toBeInTheDocument();

    const put = fetchSpy.mock.calls.find(([, init]) => init?.method === "PUT");
    expect(put[0]).toContain("/ai/ocr-policy");
    expect(JSON.parse(put[1].body)).toEqual({ enabled: false });
    expect(put[1].credentials).toBe("include");
  });

  it("explains a 403 in plain language instead of leaking the status", async () => {
    vi.stubGlobal("confirm", () => true);
    vi.stubGlobal("fetch", vi.fn((url, init) =>
      init?.method === "PUT"
        ? jsonResponse({ detail: "Only an admin can change the OCR policy" }, { ok: false, status: 403 })
        : jsonResponse(ON),
    ));

    render(<OcrPolicySection apiBase="/api" />);
    await screen.findByText("OCR + AI");
    fireEvent.click(screen.getByRole("checkbox"));

    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toMatch(/Only an admin/i));
    // The switch must not look changed when the server refused.
    expect(screen.getByRole("checkbox")).toBeChecked();
  });

  it("never shows a raw parser error when the server returns HTML", async () => {
    vi.stubGlobal("confirm", () => true);
    vi.stubGlobal("fetch", vi.fn((url, init) =>
      init?.method === "PUT"
        ? Promise.resolve({
            ok: false,
            status: 502,
            headers: { get: () => "text/html" },
            json: () => Promise.reject(new SyntaxError("Unexpected token '<'")),
          })
        : jsonResponse(ON),
    ));

    render(<OcrPolicySection apiBase="/api" />);
    await screen.findByText("OCR + AI");
    fireEvent.click(screen.getByRole("checkbox"));

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    const shown = screen.getByRole("alert").textContent;
    expect(shown).not.toMatch(/Unexpected token/);
    expect(shown).toMatch(/did not answer with a usable result/i);
  });
});
