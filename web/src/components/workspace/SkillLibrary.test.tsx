import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { SkillLibrary } from "./SkillLibrary";

vi.mock("../../api/workspace", () => ({
  listProjectSkills: vi.fn().mockResolvedValue({
    versions: [{ skill_id: "voice-check", version: 1, content: "", status: "saved", source: "author", created_at: "" }],
    enabled: [], proposals: [],
  }),
  saveProjectSkill: vi.fn(), activateProjectSkill: vi.fn(), deactivateProjectSkill: vi.fn(),
}));
afterEach(cleanup);

it("requires explicit author activation for a saved skill", async () => {
  render(<SkillLibrary projectId="p1" />);
  expect(await screen.findByRole("button", { name: "启用技能" })).toBeEnabled();
  expect(screen.queryByRole("button", { name: "停用技能" })).toBeNull();
});
