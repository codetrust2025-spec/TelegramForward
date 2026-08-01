import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";

import { AiSmartReplySettingsModal } from "./adminModule.jsx";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function json(body, { ok = true, status = 200 } = {}) {
  return Promise.resolve({
    ok,
    status,
    headers: { get: () => "application/json" },
    json: () => Promise.resolve(body),
  });
}

const OCR_ON = { enabled: true, mode: "ocr+ai", source: "environment", updated_by: "" };

/**
 * The OCR switch lives on the AI settings screen but reads its own endpoint.
 * It used to sit inside a block gated on the smart-reply config, so a single
 * unrelated 500 blanked the whole dialog — and the error message itself was
 * inside that same block, leaving an empty card with no explanation.
 */
describe("AI settings dialog when the smart-reply config fails", () => {
  function routeWith(smartReply) {
    return vi.fn((url) => {
      if (String(url).includes("/ai/ocr-policy")) return json(OCR_ON);
      return smartReply();
    });
  }

  it("still shows the OCR switch when the smart-reply config returns 500", async () => {
    vi.stubGlobal(
      "fetch",
      routeWith(() => json({ detail: "Internal Server Error" }, { ok: false, status: 500 })),
    );

    render(<AiSmartReplySettingsModal open onClose={() => {}} />);

    expect(await screen.findByText("Document reading (OCR)")).toBeInTheDocument();
    expect(screen.getByText("OCR + AI")).toBeInTheDocument();
  });

  it("surfaces the load failure instead of rendering an empty card", async () => {
    vi.stubGlobal(
      "fetch",
      routeWith(() => json({ detail: "Internal Server Error" }, { ok: false, status: 500 })),
    );

    render(<AiSmartReplySettingsModal open onClose={() => {}} />);

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(screen.getByRole("alert").textContent).toMatch(/Failed to load AI config/i);
  });

  it("still shows the OCR switch when the smart-reply fetch throws outright", async () => {
    vi.stubGlobal(
      "fetch",
      routeWith(() => Promise.reject(new Error("network down"))),
    );

    render(<AiSmartReplySettingsModal open onClose={() => {}} />);

    expect(await screen.findByText("Document reading (OCR)")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("alert").textContent).toMatch(/network down/i));
  });

  it("does not duplicate the error once the config loads", async () => {
    vi.stubGlobal(
      "fetch",
      routeWith(() => json({ status: "ok", config: { enabled: false }, health: { api_key_present: true } })),
    );

    render(<AiSmartReplySettingsModal open onClose={() => {}} />);

    expect(await screen.findByText("Document reading (OCR)")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
