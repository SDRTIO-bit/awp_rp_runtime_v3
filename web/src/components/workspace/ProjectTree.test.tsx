import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ProjectTree } from "./ProjectTree";

vi.mock("../../api/workspace", () => ({
  listChapters: vi.fn().mockResolvedValue([]),
}));

afterEach(cleanup);

it("exposes AI model settings as a first-level project tool", () => {
  const onPrompt = vi.fn();
  render(<ProjectTree projectId="p1" room="book" onRoom={vi.fn()} onPrompt={onPrompt} />);

  const button = screen.getByRole("button", { name: /AI 模型设置/ });
  expect(screen.getByText(/供应商、模型与角色提示词/)).toBeVisible();
  fireEvent.click(button);
  expect(onPrompt).toHaveBeenCalledOnce();
});
