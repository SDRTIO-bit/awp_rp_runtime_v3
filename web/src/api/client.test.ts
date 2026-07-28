import { expect, it, vi } from "vitest";
import { updateLlmConfig } from "./client";

const BASE = "";

async function put<T>(path: string, payload?: unknown): Promise<T> {
  const res = await fetch(`${BASE}/awp/api/v1${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload ?? {}),
  });
  const body = (await res.json()) as { data?: T };
  if (!res.ok) throw new Error(typeof body?.data === "object" && body.data !== null && "error" in body.data ? String((body.data as Record<string, unknown>).error) : `Request failed (${res.status})`);
  return body.data as T;
}

it("sends PUT with Content-Type JSON and body", async () => {
  globalThis.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ data: { ok: true, overrides: {} } }),
  } as Response);

  const result = await put("/novels/test-proj/llm-config", { overrides: { writer: { model: "gpt-5" } } });
  expect(result).toEqual({ ok: true, overrides: {} });
  const [url, init] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
  expect(url).toContain("/awp/api/v1/novels/test-proj/llm-config");
  expect(init.method).toBe("PUT");
  const parsed = JSON.parse(init.body as string);
  expect(parsed.overrides.writer.model).toBe("gpt-5");
});

it("throws on non-ok response", async () => {
  globalThis.fetch = vi.fn().mockResolvedValue({
    ok: false,
    status: 405,
    json: async () => ({ data: { error: "method not allowed" } }),
  } as Response);

  await expect(put("/novels/x/llm-config", {})).rejects.toThrow("method not allowed");
});

it("reports a non-JSON response instead of surfacing a JSON syntax error", async () => {
  globalThis.fetch = vi.fn().mockResolvedValue({
    ok: false,
    status: 405,
    headers: new Headers({ "Content-Type": "text/plain" }),
    text: async () => "Method Not Allowed",
  } as Response);

  await expect(updateLlmConfig("x", {})).rejects.toThrow("HTTP 405: expected JSON but received Method Not Allowed");
});
