import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { updateLlmConfig } from "../api/client";
import PromptStudio from "./PromptStudio";

vi.mock("../api/workspace", () => ({
  listPrompts: vi.fn().mockResolvedValue([]),
  getPrompt: vi.fn().mockResolvedValue({ content: "", revision: 1, source: "system", role: "editor" }),
  savePrompt: vi.fn(),
  promptDiff: vi.fn(),
}));
vi.mock("../api/client", () => ({
  getLlmConfig: vi.fn().mockResolvedValue({
    overrides: {},
    defaults: { brain: { provider: "opencode", model: "qwen3.7-plus", max_tokens: 4000, thinking_level: "low" } },
  }),
  updateLlmConfig: vi.fn().mockResolvedValue({ ok: true, overrides: {} }),
  testLlmConnection: vi.fn().mockResolvedValue({ ok: true, model_count: 2 }),
  listLlmModels: vi.fn().mockResolvedValue({ models: ["model-a", "model-b"] }),
}));

afterEach(cleanup);

it("opens directly on the LLM tab when requested by URL", async () => {
  render(
    <MemoryRouter initialEntries={["/novels/p1/prompts?tab=llm"]}>
      <Routes><Route path="/novels/:id/prompts" element={<PromptStudio />} /></Routes>
    </MemoryRouter>,
  );

  expect(await screen.findAllByText("LLM 模型配置")).toHaveLength(2);
  expect(screen.getByText("供应商：opencode")).toBeVisible();
});

it("tests the current editor configuration and offers discovered models", async () => {
  const user = userEvent.setup();
  render(
    <MemoryRouter initialEntries={["/novels/p1/prompts?tab=llm"]}>
      <Routes><Route path="/novels/:id/prompts" element={<PromptStudio />} /></Routes>
    </MemoryRouter>,
  );

  await user.click(await screen.findByRole("button", { name: "编辑配置" }));
  await user.click(screen.getByRole("button", { name: "测试连接" }));
  expect(await screen.findByText("连接成功，可读取 2 个模型。")) .toBeVisible();

  await user.click(screen.getByRole("button", { name: "获取模型列表" }));
  expect(await screen.findByRole("option", { name: "model-a" })).toBeVisible();
  expect(updateLlmConfig).toHaveBeenCalledWith("p1", {});
});
