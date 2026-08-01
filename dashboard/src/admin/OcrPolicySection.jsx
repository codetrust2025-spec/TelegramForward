import React, { useCallback, useEffect, useState } from "react";

import { MODE_LABELS } from "../components/AiProcessingStatus.jsx";

/**
 * Admin-only control for the global OCR switch.
 *
 * Turning OCR off disables Tesseract across the whole project — invite
 * extraction, screenshot parsing, payment and proof reading — leaving Ollama to
 * do everything. That is a wide blast radius for one click, so the change is
 * confirmed first and the consequence is spelled out rather than implied.
 *
 * @param {object} props
 * @param {string} props.apiBase
 * @param {(msg: string) => void} [props.setError]
 */
export function OcrPolicySection({ apiBase, setError }) {
  const [policy, setPolicy] = useState(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [failure, setFailure] = useState("");

  const load = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase}/ai/ocr-policy`, { credentials: "include" });
      const contentType = String(res.headers?.get?.("content-type") || "");
      if (!res.ok || !contentType.includes("application/json")) {
        throw new Error("Could not read the OCR setting.");
      }
      setPolicy(await res.json());
      setFailure("");
    } catch (err) {
      setFailure(err.message || "Could not read the OCR setting.");
    }
  }, [apiBase]);

  useEffect(() => { load(); }, [load]);

  const toggle = useCallback(async () => {
    if (!policy || busy) return;
    const turningOff = policy.enabled;
    const confirmed = window.confirm(
      turningOff
        ? "Turn OCR OFF for the whole project?\n\n"
          + "Tesseract stops running everywhere — invite extraction, screenshot "
          + "parsing, payment and proof reading. Ollama AI handles all of it "
          + "alone, so some reads may fail and need manual entry."
        : "Turn OCR ON for the whole project?\n\n"
          + "Tesseract runs alongside Ollama again and cross-checks what the AI reads.",
    );
    if (!confirmed) return;

    setBusy(true);
    setNotice("");
    setFailure("");
    try {
      const res = await fetch(`${apiBase}/ai/ocr-policy`, {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: !policy.enabled }),
      });
      const contentType = String(res.headers?.get?.("content-type") || "");
      if (!contentType.includes("application/json")) {
        throw new Error("The server did not answer with a usable result.");
      }
      const data = await res.json();
      if (!res.ok) {
        throw new Error(
          res.status === 403
            ? "Only an admin can change the OCR setting."
            : data.detail || data.message || "Could not change the OCR setting.",
        );
      }
      setPolicy(data);
      setNotice(`OCR is now ${data.enabled ? "ON" : "OFF"} — ${MODE_LABELS[data.mode]}.`);
    } catch (err) {
      const message = err.message || "Could not change the OCR setting.";
      setFailure(message);
      setError?.(message);
    } finally {
      setBusy(false);
    }
  }, [apiBase, busy, policy, setError]);

  if (!policy) {
    return (
      <section className="ai-settings-row ocr-policy">
        <span className="ai-settings-row-hint">
          {failure || "Loading the OCR setting…"}
        </span>
      </section>
    );
  }

  return (
    <section className="ai-settings-row ai-settings-row--toggle ocr-policy">
      <span>
        <strong>Document reading (OCR)</strong>
        <span className="ocr-policy__mode" data-mode={policy.mode}>
          {MODE_LABELS[policy.mode] || policy.mode}
        </span>
        <span className="ai-settings-row-hint">
          When on, Tesseract reads images alongside Ollama and cross-checks the
          result. When off, <strong>OCR never runs anywhere in the project</strong> and
          Ollama handles every image on its own.
          {policy.source === "admin" && policy.updated_by && (
            <> Last changed by {policy.updated_by}.</>
          )}
          {policy.source === "environment" && <> Currently from the server environment.</>}
        </span>
        {notice && <span className="ocr-policy__notice" role="status">{notice}</span>}
        {failure && <span className="ocr-policy__error" role="alert">{failure}</span>}
      </span>
      <input
        type="checkbox"
        checked={!!policy.enabled}
        disabled={busy}
        onChange={toggle}
        aria-label={`OCR is ${policy.enabled ? "on" : "off"}`}
      />
    </section>
  );
}

export default OcrPolicySection;
