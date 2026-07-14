import test from "node:test";
import assert from "node:assert/strict";

import { createNovelTools } from "../src/novel_tools.mjs";

test("only five project-bound novel tools exist", () => {
  const tools = createNovelTools(async () => ({ ok: true, content: "ok" }));

  assert.deepEqual(tools.map((tool) => tool.name), [
    "project_status",
    "read_chapter",
    "plan_chapter",
    "write_chapter",
    "audit_chapter",
  ]);
  assert.equal(
    tools.some((tool) => ["bash", "read", "write", "edit"].includes(tool.name)),
    false,
  );
});
