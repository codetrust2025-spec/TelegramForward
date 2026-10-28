import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import AiMailModelSelector from "./AiMailModelSelector.jsx";

afterEach(cleanup);
const inventory = () => ({ selection: { model: "old:7b", revision: 4,
  last_used: { model: "old:7b", node_id: "rtx4060", node_label: "RTX 4060" } },
nodes: [{ id: "rtx4060", label: "RTX 4060", available: true, models: [
  { name: "old:7b", size_bytes: 4 * 1024 ** 3 }, { name: "new:8b", size_bytes: 5 * 1024 ** 3 }] },
{ id: "backup", label: "Other node", available: false, models: [] }] });

describe("AI Mail model selector", () => {
  it("recognizes the configured latest alias as installed", async () => {
    const data = inventory();
    data.selection.model = "alias";
    data.nodes[0].models.push({ name: "alias:latest", size_bytes: 1024 ** 3 });
    render(<AiMailModelSelector request={vi.fn().mockResolvedValue(data)} />);
    expect(await screen.findByRole("option", { name: "alias — available (configured alias)" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Test model & failover" })).toBeEnabled();
  });
  it("shows installed size, availability, configured model and actual node", async () => {
    render(<AiMailModelSelector request={vi.fn().mockResolvedValue(inventory())} />);
    expect(await screen.findByText(/Last actual AI Mail execution: old:7b on RTX 4060/)).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /new:8b.*5.0 GiB.*available/ })).toBeInTheDocument();
    expect(screen.getByText(/Other node: offline/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save AI Mail model" })).toBeDisabled();
  });
  it("tests before saving, sends revision and changes configuration only after success", async () => {
    const request = vi.fn(async (path, options) => {
      if (!options) return inventory();
      if (options.method === "PUT") return { selection: { model: "new:8b", revision: 5 } };
      return { ok: true };
    });
    render(<AiMailModelSelector request={request} />);
    fireEvent.change(await screen.findByRole("combobox"), { target: { value: "new:8b" } });
    fireEvent.click(screen.getByRole("button", { name: "Test model & failover" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Save AI Mail model" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "Save AI Mail model" }));
    await screen.findByText(/AI Mail model saved/);
    expect(request).toHaveBeenCalledWith("/api/ai-recruitment/mail-model", {
      method: "PUT", body: JSON.stringify({ model: "new:8b", revision: 4 }),
    });
    expect(screen.getByText("new:8b", { selector: "strong" })).toBeInTheDocument();
  });
  it("keeps previous configuration and disables save after validation fails", async () => {
    const request = vi.fn(async (path, options) => {
      if (options) throw new Error("Structured JSON validation failed");
      return inventory();
    });
    render(<AiMailModelSelector request={request} />);
    await screen.findByText("old:7b", { selector: "strong" });
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "new:8b" } });
    fireEvent.click(screen.getByRole("button", { name: "Test model & failover" }));
    await screen.findByText(/Previous configured model retained/);
    expect(screen.getByText("old:7b", { selector: "strong" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save AI Mail model" })).toBeDisabled();
  });
  it("invalidates test result when the selected model changes", async () => {
    const request = vi.fn().mockResolvedValue(inventory());
    render(<AiMailModelSelector request={request} />);
    await screen.findByText("old:7b", { selector: "strong" });
    fireEvent.click(screen.getByRole("button", { name: "Test model & failover" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Save AI Mail model" })).toBeEnabled());
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "new:8b" } });
    expect(screen.getByRole("button", { name: "Save AI Mail model" })).toBeDisabled();
  });
});
