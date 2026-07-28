import test from "node:test";
import assert from "node:assert/strict";

import { createNovelTools } from "../src/novel_tools.mjs";

test("only sandboxed project and authoring tools exist", () => {
  const tools = createNovelTools(async () => ({ ok: true, content: "ok" }));

  assert.deepEqual(tools.map((tool) => tool.name).sort(), [
    "read",
    "ls",
    "find",
    "grep",
    "write",
    "edit",
    "bash",
    "delegate_project_task",
    "project_status",
    "read_chapter",
    "save_revision_plan",
    "approve_revision_plan",
    "apply_revision_plan",
    "propose_project_skill",
    "audit_chapter",
    "read_authoring_context",
    "capture_author_material",
    "save_author_plan",
    "approve_author_plan",
    "execute_author_plan",
    "update_work_plan",
  ].sort());
  assert.equal(tools.some((tool) => tool.name === "fetch_url"), false);
  assert.equal(tools.some((tool) => ["plan_chapter", "write_chapter"].includes(tool.name)), false);
});
