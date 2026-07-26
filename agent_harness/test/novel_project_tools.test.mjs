import test from "node:test";
import assert from "node:assert/strict";

import { createNovelProjectTools } from "../src/novel_project_tools.mjs";


test("project tool schemas expose coding names through Python RPC", async () => {
  const calls = [];
  const tools = createNovelProjectTools(async (name, args) => {
    calls.push([name, args]);
    return { content: "ok" };
  });

  assert.deepEqual(
    tools.map((tool) => tool.name),
    ["read", "ls", "find", "grep", "write", "edit", "bash", "delegate_project_task"],
  );
  const read = tools.find((tool) => tool.name === "read");
  const result = await read.execute("t1", { path: "outline.md" });

  assert.deepEqual(calls[0], ["read", { path: "outline.md" }]);
  assert.equal(result.content[0].text, "ok");
});


test("project tools reject unknown arguments before Python execution", async () => {
  const tools = createNovelProjectTools(async () => ({ content: "ok" }));
  const write = tools.find((tool) => tool.name === "write");

  assert.equal(write.parameters.additionalProperties, false);
  assert.deepEqual(write.parameters.required.sort(), ["content", "path"]);
});
