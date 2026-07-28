import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { AuthorPlanCard } from "./AuthorPlanCard";

afterEach(cleanup);

it("blocks confirmation while unresolved questions remain", async () => {
  const onApprove = vi.fn();
  render(
    <AuthorPlanCard
      plan={{
        plan_id: "chapter-1",
        revision: 1,
        status: "pending_confirmation",
        unresolved_questions: ["持钥人为什么选中陈默？"],
      }}
      onApprove={onApprove}
      onExecute={vi.fn()}
    />,
  );

  const confirm = screen.getByRole("button", { name: "确认计划" });
  expect(confirm).toBeDisabled();
  await userEvent.click(confirm);
  expect(onApprove).not.toHaveBeenCalled();
  expect(screen.getByRole("button", { name: "交给管线写作" })).toBeDisabled();
  expect(screen.getByText("确认前需要补充：持钥人为什么选中陈默？")).toBeVisible();
});


it("enables confirmation for a plan without unresolved questions", () => {
  render(
    <AuthorPlanCard
      plan={{ plan_id: "chapter-1", revision: 1, status: "pending_confirmation" }}
      onApprove={vi.fn()}
      onExecute={vi.fn()}
    />,
  );

  expect(screen.getByRole("button", { name: "确认计划" })).toBeEnabled();
  expect(screen.getByRole("button", { name: "交给管线写作" })).toBeDisabled();
});
