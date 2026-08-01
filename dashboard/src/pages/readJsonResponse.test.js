import { describe, expect, it } from "vitest";

import {
  INVITE_READ_FAILED_MESSAGE,
  readJsonResponse,
} from "./SubmitSlotPage.jsx";

/**
 * Ollama invite extraction can outrun the proxy. Nginx then answers with an
 * HTML 504 page (a restarting backend gives an HTML 502 the same way), and the
 * old code called res.json() on it — surfacing the raw
 * `Unexpected token '<', "<html>..."` SyntaxError to the candidate.
 */
function response({ body, contentType, status = 200, throwOnJson = false }) {
  return {
    status,
    headers: { get: (name) => (name.toLowerCase() === "content-type" ? contentType : null) },
    json: async () => {
      if (throwOnJson) throw new SyntaxError("Unexpected token '<'");
      return body;
    },
  };
}

const HTML_504 =
  "<html>\r\n<head><title>504 Gateway Time-out</title></head>\r\n<body>...";
const HTML_502 =
  "<html>\r\n<head><title>502 Bad Gateway</title></head>\r\n<body>...";

describe("readJsonResponse", () => {
  it("returns the parsed body for a successful JSON response", async () => {
    const payload = { status: "ok", data: { interview_date: "2026-08-05" } };
    await expect(
      readJsonResponse(
        response({ body: payload, contentType: "application/json" }),
      ),
    ).resolves.toEqual(payload);
  });

  it("accepts a JSON content-type carrying a charset", async () => {
    await expect(
      readJsonResponse(
        response({
          body: { status: "ok" },
          contentType: "application/json; charset=utf-8",
        }),
      ),
    ).resolves.toEqual({ status: "ok" });
  });

  it("rejects an Nginx HTML 504 page instead of parsing it", async () => {
    await expect(
      readJsonResponse(
        response({
          body: HTML_504,
          contentType: "text/html",
          status: 504,
          throwOnJson: true,
        }),
      ),
    ).rejects.toThrow(/Expected JSON/);
  });

  it("rejects an Nginx HTML 502 page instead of parsing it", async () => {
    await expect(
      readJsonResponse(
        response({
          body: HTML_502,
          contentType: "text/html",
          status: 502,
          throwOnJson: true,
        }),
      ),
    ).rejects.toThrow(/Expected JSON/);
  });

  it("never lets the raw SyntaxError text escape", async () => {
    let message = "";
    try {
      await readJsonResponse(
        response({
          body: HTML_504,
          contentType: "text/html",
          status: 504,
          throwOnJson: true,
        }),
      );
    } catch (error) {
      message = String(error?.message || "");
    }
    expect(message).not.toMatch(/Unexpected token/);
    expect(message).not.toMatch(/<html>/);
  });

  it("rejects malformed JSON even when the content-type claims JSON", async () => {
    await expect(
      readJsonResponse(
        response({
          contentType: "application/json",
          status: 200,
          throwOnJson: true,
        }),
      ),
    ).rejects.toThrow(/Malformed JSON/);
  });

  it("rejects an empty body", async () => {
    await expect(
      readJsonResponse(
        response({ body: null, contentType: "application/json" }),
      ),
    ).rejects.toThrow(/Empty or unusable/);
  });

  it("rejects a non-object JSON body", async () => {
    await expect(
      readJsonResponse(
        response({ body: "just a string", contentType: "application/json" }),
      ),
    ).rejects.toThrow(/Empty or unusable/);
  });

  it("rejects a response with no content-type at all", async () => {
    await expect(
      readJsonResponse(response({ body: {}, contentType: null })),
    ).rejects.toThrow(/Expected JSON/);
  });

  it("exposes candidate-safe copy that names the manual fallback", () => {
    expect(INVITE_READ_FAILED_MESSAGE).toBe(
      "Could not read the invite. Retry or enter date and time manually.",
    );
    expect(INVITE_READ_FAILED_MESSAGE).not.toMatch(/JSON|token|<html>|HTTP/i);
  });
});
