import test from "node:test";
import assert from "node:assert/strict";

import { createNovelTools } from "../src/novel_tools.mjs";

test("only sandboxed project and authoring tools exist", () => {
  const tools = createNovelTools(async () => ({ ok: true, content: "ok" }));

  assert.deepEqual(tools.map((tool) => tool.name), [
    "read",
    "ls",
    "find",
    "grep",
    "write",
    "edit",
    "bash",
    "delegate_project_task",
    "update_work_plan",
    "project_status",
    "read_chapter",
    "audit_chapter",
    "read_authoring_context",
    "capture_author_material",
    "save_author_plan",
    "approve_author_plan",
    "execute_author_plan",
  ]);
  assert.equal(tools.some((tool) => tool.name === "fetch_url"), false);
  assert.equal(tools.some((tool) => ["plan_chapter", "write_chapter"].includes(tool.name)), false);
});
