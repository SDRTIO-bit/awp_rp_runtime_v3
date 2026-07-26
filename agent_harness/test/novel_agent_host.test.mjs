import test from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";

import { createNovelAgentSession, NOVEL_TOOL_NAMES, NovelAgentHost } from "../src/novel_agent_host.mjs";

test("host initializes Pi with no builtins and only editor tools", async () => {
  let options;
  const frames = [];
  const fakeSession = {
    subscribe: () => {},
    dispose: () => {},
  };
  const host = new NovelAgentHost({
    createSession: async (received) => {
      options = received;
      return { session: fakeSession };
    },
    writeFrame: (frame) => frames.push(frame),
  });

  await host.handleFrame({
    kind: "init",
    request_id: "init-1",
    payload: { project_root: "C:/novel", session_dir: "C:/sessions", connection: {} },
  });

  assert.equal(options.project_root, "C:/novel");
  assert.deepEqual(NOVEL_TOOL_NAMES, [
    "project_status", "read_chapter", "audit_chapter",
    "read_authoring_context", "capture_author_material", "save_author_plan",
    "approve_author_plan", "execute_author_plan",
  ]);
  assert.deepEqual(frames, [{ kind: "event", request_id: "init-1", payload: { type: "ready" } }]);
});

test("real session factory receives the closed tool configuration", async () => {
  let captured;
  await createNovelAgentSession(
    {
      project_root: process.cwd(),
      session_dir: `${process.cwd()}/.test-sessions`,
      connection: {
        provider: "test-provider",
        model: "test-model",
        base_url: "https://example.invalid/v1",
        api_key_env: "TEST_API_KEY",
      },
    },
    async () => ({ content: "ok" }),
    fileURLToPath(new URL("../resources", import.meta.url)),
    { createSession: async (options) => { captured = options; return { session: { dispose: () => {} } }; } },
  );

  assert.equal(captured.noTools, "all");
  assert.deepEqual(captured.tools, NOVEL_TOOL_NAMES);
  assert.deepEqual(captured.customTools.map((tool) => tool.name), NOVEL_TOOL_NAMES);
});
