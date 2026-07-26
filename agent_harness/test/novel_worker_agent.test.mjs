import test from "node:test";
import assert from "node:assert/strict";

import { createProjectWorkerAgent } from "../src/novel_worker_agent.mjs";


const init = {
  project_root: process.cwd(),
  session_dir: `${process.cwd()}/.test-worker-sessions`,
  connection: {
    provider: "test-provider",
    model: "test-model",
    base_url: "https://example.invalid/v1",
    api_key_env: "TEST_API_KEY",
    thinking_level: "low",
  },
};


test("worker receives only read-only project tools and cannot delegate", async () => {
  let captured;
  let disposed = false;
  const worker = await createProjectWorkerAgent(
    init,
    async () => ({ content: "ok" }),
    {
      createSessionManager: () => ({}),
      createSession: async (options) => {
        captured = options;
        return {
          session: {
            prompt: async () => {},
            getLastAssistantText: () => "证据：world.md:1",
            dispose: () => { disposed = true; },
          },
        };
      },
    },
  );

  const result = await worker.run({ task: "核对礼堂设定", max_files: 20 });

  assert.deepEqual(captured.tools, ["read", "ls", "find", "grep"]);
  assert.equal(captured.tools.includes("write"), false);
  assert.equal(captured.tools.includes("delegate_project_task"), false);
  assert.deepEqual(
    captured.customTools.map((tool) => tool.name),
    ["read", "ls", "find", "grep"],
  );
  assert.match(result, /world\.md:1/);
  assert.equal(disposed, true);
});


test("worker rejects invalid focus paths before creating a session", async () => {
  let created = false;
  const worker = await createProjectWorkerAgent(
    init,
    async () => ({ content: "ok" }),
    {
      createSessionManager: () => ({}),
      createSession: async () => {
        created = true;
        throw new Error("must not run");
      },
    },
  );

  await assert.rejects(
    worker.run({ task: "读取", focus_paths: ["../outside.md"] }),
    /project-relative/,
  );
  assert.equal(created, false);
});
