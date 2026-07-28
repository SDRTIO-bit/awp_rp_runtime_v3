import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ToolActivity } from "./ToolActivity";

afterEach(cleanup);

it("renders recent completed tools as a compact strip", () => {
  const { container } = render(
    <ToolActivity
      activity={{ read: { approval_id: "read", tool: "read", status: "completed", summary: "读取 outline.md" } }}
      approvals={{}}
      onDecision={vi.fn()}
    />,
  );

  expect(screen.getByRole("region", { name: "编辑工具活动" })).toHaveClass("compact");
  expect(screen.queryByText("需要你的审批")).not.toBeInTheDocument();
  expect(container.querySelector(".tool-activity-strip")).toBeVisible();
});

it("renders pending approval actions instead of the recent strip", () => {
  render(
    <ToolActivity
      activity={{}}
      approvals={{ approve: { approval_id: "approve", tool: "write", status: "waiting", summary: "修改 outline.md" } }}
      onDecision={vi.fn()}
    />,
  );

  expect(screen.getByRole("region", { name: "编辑工具活动" })).toHaveClass("pending");
  expect(screen.getByText("需要你的审批")).toBeVisible();
  expect(screen.getByRole("button", { name: "本次允许" })).toBeEnabled();
});
