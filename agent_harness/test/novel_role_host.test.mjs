import test from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";

import {
  NovelRoleHost,
  createNovelRoleSession,
} from "../src/novel_role_host.mjs";
import { ROLE_TOOL_ALLOWLISTS } from "../src/novel_role_tools.mjs";


const resourcesRoot = fileURLToPath(new URL("../resources/roles", import.meta.url));

function task(overrides = {}) {
  return {
    role: "writer",
    project_id: "p1",
    chapter_index: 4,
    revision: 1,
    phase: "beat:0",
    session_key: "p1:4:1:writer",
    task_contract: "Write the requested beat and return only prose.",
    input_payload: { prompt: "写第一拍" },
    stream: true,
    connection: {
      provider: "test-provider",
      model: "test-model",
      base_url: "https://example.invalid/v1",
      api_key_env: "TEST_API_KEY",
    },
    max_tokens: 4096,
    thinking_level: "medium",
    ...overrides,
  };
}

function fakeSession(text = "正文") {
  const listeners = [];
  return {
    model: { id: "test-model" },
    subscribe(listener) { listeners.push(listener); },
    async prompt(promptText) {
      this.lastPrompt = promptText;
      for (const listener of listeners) {
        listener({
          type: "message_update",
          assistantMessageEvent: { type: "text_delta", delta: text },
        });
      }
    },
    getLastAssistantText: () => text,
    getSessionStats: () => ({
      tokens: { input: 10, output: 20, cacheRead: 3, cacheWrite: 1, total: 34 },
    }),
    async abort() {},
    dispose() { this.disposed = true; },
  };
}

test("role session factory creates a real Pi session with no built-in tools", async () => {
  let captured;
  await createNovelRoleSession(
    task(),
    {
      project_root: process.cwd(),
      session_dir: `${process.cwd()}/.role-test-session`,
    },
    async () => ({ content: "ok" }),
    resourcesRoot,
    { createSession: async (options) => { captured = options; return { session: fakeSession() }; } },
  );

  assert.equal(captured.noTools, "all");
  assert.deepEqual(captured.tools, ROLE_TOOL_ALLOWLISTS.writer);
  assert.deepEqual(captured.customTools.map((tool) => tool.name), ROLE_TOOL_ALLOWLISTS.writer);
  assert.match(captured.resourceLoader.getSystemPrompt(), /Writer/);
});

test("writer reuses only the same chapter revision Pi session", async () => {
  let createdSessions = 0;
  const sessions = [];
  const host = new NovelRoleHost({
    createSession: async () => {
      createdSessions += 1;
      const created = fakeSession(`draft-${createdSessions}`);
      sessions.push(created);
      return { session: created };
    },
    writeFrame: () => {},
  });
  await host.handleFrame({
    kind: "role_init",
    request_id: "init",
    payload: { project_id: "p1", project_root: process.cwd(), session_root: ".sessions" },
  });

  await host.handleFrame({ kind: "role_prompt", request_id: "r1", payload: task() });
  await host.handleFrame({ kind: "role_prompt", request_id: "r2", payload: task({ phase: "beat:1" }) });
  await host.handleFrame({
    kind: "role_prompt",
    request_id: "r3",
    payload: task({ revision: 2, session_key: "p1:4:2:writer" }),
  });

  assert.equal(createdSessions, 2);
  assert.equal(sessions[0].disposed, undefined);
  assert.match(sessions[0].lastPrompt, /beat:1/);
});

test("task-scoped role is disposed after role_end", async () => {
  const frames = [];
  const session = fakeSession("{\"beats\":[]}");
  const host = new NovelRoleHost({
    createSession: async () => ({ session }),
    writeFrame: (frame) => frames.push(frame),
  });
  await host.handleFrame({
    kind: "role_init",
    request_id: "init",
    payload: { project_id: "p1", project_root: process.cwd(), session_root: ".sessions" },
  });
  await host.handleFrame({
    kind: "role_prompt",
    request_id: "director-1",
    payload: task({
      role: "director",
      session_key: "task:director-1",
      stream: false,
    }),
  });

  assert.equal(session.disposed, true);
  const end = frames.find((frame) => frame.kind === "role_end");
  assert.equal(end.payload.role, "director");
  assert.equal(end.payload.text, "{\"beats\":[]}");
  assert.deepEqual(end.payload.usage, {
    input: 10, output: 20, cache_read: 3, cache_write: 1, total: 34,
  });
});

test("close_session disposes the retained writer session", async () => {
  const session = fakeSession();
  const frames = [];
  const host = new NovelRoleHost({
    createSession: async () => ({ session }),
    writeFrame: (frame) => frames.push(frame),
  });
  await host.handleFrame({
    kind: "role_init",
    request_id: "init",
    payload: { project_id: "p1", project_root: process.cwd(), session_root: ".sessions" },
  });
  await host.handleFrame({ kind: "role_prompt", request_id: "r1", payload: task() });
  await host.handleFrame({
    kind: "close_session",
    request_id: "close-1",
    payload: { session_key: "p1:4:1:writer" },
  });

  assert.equal(session.disposed, true);
  assert.ok(frames.some((frame) => frame.kind === "event" && frame.payload.type === "session_closed"));
});

test("host rejects a task for a different bound project", async () => {
  const frames = [];
  const host = new NovelRoleHost({
    createSession: async () => ({ session: fakeSession() }),
    writeFrame: (frame) => frames.push(frame),
  });
  await host.handleFrame({
    kind: "role_init",
    request_id: "init",
    payload: { project_id: "p1", project_root: process.cwd(), session_root: ".sessions" },
  });
  await host.handleFrame({
    kind: "role_prompt",
    request_id: "wrong-project",
    payload: task({ project_id: "p2" }),
  });

  assert.ok(frames.some((frame) => frame.kind === "error" && /different project/.test(frame.payload.message)));
});
