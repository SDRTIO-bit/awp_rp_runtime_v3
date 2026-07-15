import test from "node:test";
import assert from "node:assert/strict";

import {
  ROLE_TOOL_ALLOWLISTS,
  createRoleTools,
} from "../src/novel_role_tools.mjs";


test("writer gets only its project-bound read tools", () => {
  const tools = createRoleTools("writer", async () => ({ content: "ok" }));
  const names = tools.map((tool) => tool.name);

  assert.deepEqual(names, ROLE_TOOL_ALLOWLISTS.writer);
  assert(names.includes("read_write_packet"));
  assert(!names.includes("write_chapter"));
  assert(!names.includes("plan_chapter"));
  assert(!names.includes("bash"));
});


test("style cleaner has no tools", () => {
  assert.deepEqual(createRoleTools("style_cleaner", async () => ({})), []);
});


test("unknown role is rejected instead of inheriting tools", () => {
  assert.throws(
    () => createRoleTools("shell", async () => ({})),
    /unsupported Pi novel role/,
  );
});

