import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { RevisionPane } from "./RevisionPane";

it("shows revision-local paragraph references while keeping prose read-only", () => {
  render(<RevisionPane chapter={{ chapter_index: 2, title: "第二章", draft_id: "draft-ch2-r2", accepted_revision: 2, text_sha256: "a".repeat(64), paragraphs: [
    { paragraph_id: "r2:p1", ordinal: 1, text: "第一段", sha256: "b".repeat(64) },
  ] }} />);
  expect(screen.getByText("基于正文 r2 · draft-ch2-r2")).toBeVisible();
  expect(screen.getByText("r2:p1")).toBeVisible();
  expect(screen.queryByRole("button", { name: "应用修订" })).toBeNull();
});
