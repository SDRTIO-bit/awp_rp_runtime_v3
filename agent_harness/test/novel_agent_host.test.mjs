import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { createClosedResourceLoader, createNovelAgentSession, NOVEL_TOOL_NAMES, NovelAgentHost } from "../src/novel_agent_host.mjs";

const resourcesRoot = fileURLToPath(new URL("../resources", import.meta.url));

test("host initializes Pi with closed project and editor tools", async () => {
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
    "read", "ls", "find", "grep", "write", "edit", "bash",
    "delegate_project_task",
    "update_work_plan",
    "project_status", "read_chapter", "save_revision_plan",
    "approve_revision_plan", "apply_revision_plan", "propose_project_skill", "audit_chapter",
    "read_authoring_context", "capture_author_material", "save_author_plan",
    "approve_author_plan", "execute_author_plan",
  ]);
  assert.deepEqual(frames, [{ kind: "event", request_id: "init-1", payload: { type: "ready" } }]);
});

test("editor loader includes only manifest-enabled project skills", () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), "awp-editor-skills-"));
  try {
    const enabled = path.join(projectRoot, "agent", "skills", "voice-check");
    const disabled = path.join(projectRoot, "agent", "skills", "stray");
    fs.mkdirSync(enabled, { recursive: true });
    fs.mkdirSync(disabled, { recursive: true });
    fs.writeFileSync(path.join(enabled, "SKILL.md"), "---\nname: voice-check\ndescription: enabled\n---\n正文\n");
    fs.writeFileSync(path.join(disabled, "SKILL.md"), "---\nname: stray\ndescription: disabled\n---\n正文\n");
    fs.mkdirSync(path.join(projectRoot, ".awp"), { recursive: true });
    fs.writeFileSync(
      path.join(projectRoot, ".awp", "enabled-project-skills.json"),
      JSON.stringify({ skills: [{ skill_id: "voice-check", version: 1 }] }),
    );

    const names = createClosedResourceLoader(resourcesRoot, projectRoot)
      .getSkills().skills.map((skill) => skill.name);

    assert(names.includes("voice-check"));
    assert(!names.includes("stray"));
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});

test("editor tool calls use the active prompt request id", async () => {
  const frames = [];
  let requestPython;
  let finishTurn;
  const turnFinished = new Promise((resolve) => { finishTurn = resolve; });
  const fakeSession = {
    subscribe: () => {},
    dispose: () => {},
    prompt: async () => {
      await requestPython("project_status", {}, undefined);
    },
    getLastAssistantText: () => "已读取项目状态",
  };
  let host;
  host = new NovelAgentHost({
    createSession: async (_payload, receivedRequestPython) => {
      requestPython = receivedRequestPython;
      return { session: fakeSession };
    },
    writeFrame: (frame) => {
      frames.push(frame);
      if (frame.kind === "tool_call") {
        void host.handleFrame({
          kind: "tool_result",
          request_id: frame.request_id,
          payload: {
            tool_call_id: frame.payload.tool_call_id,
            ok: true,
            content: "项目正常",
          },
        });
      }
      if (frame.kind === "turn_end") finishTurn();
    },
  });

  await host.handleFrame({
    kind: "init",
    request_id: "init-1",
    payload: { project_root: "C:/novel", session_dir: "C:/sessions", connection: {} },
  });
  await host.handleFrame({
    kind: "prompt",
    request_id: "prompt-1",
    payload: { text: "读取项目状态" },
  });
  await turnFinished;

  const toolCall = frames.find((frame) => frame.kind === "tool_call");
  assert.equal(toolCall?.request_id, "prompt-1");
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
  assert.deepEqual([...captured.tools].sort(), [...NOVEL_TOOL_NAMES].sort());
  assert.deepEqual(captured.customTools.map((tool) => tool.name).sort(), [...NOVEL_TOOL_NAMES].sort());
  const skills = captured.resourceLoader.getSkills().skills;
  const collaboration = skills.find((skill) => skill.name === "author-collaboration");
  assert.equal(collaboration?.disableModelInvocation, false);
  const systemPrompt = captured.resourceLoader.getSystemPrompt();
  assert.match(systemPrompt, /作品和目标读者/);
  assert.match(systemPrompt, /不得直接创作整章正文/);
  assert.match(systemPrompt, /自动使用.*author-collaboration/s);
  assert.match(systemPrompt, /先读取已有项目/s);
  assert.match(systemPrompt, /不得用工具.*替作者决定剧情/s);
});
