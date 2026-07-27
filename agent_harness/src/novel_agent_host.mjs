import fs from "node:fs";
import path from "node:path";
import readline from "node:readline";
import { randomUUID } from "node:crypto";
import { fileURLToPath } from "node:url";

import {
  AuthStorage,
  createAgentSession,
  createExtensionRuntime,
  createSyntheticSourceInfo,
  ModelRegistry,
  SessionManager,
  SettingsManager,
} from "@earendil-works/pi-coding-agent";

import { createNovelTools } from "./novel_tools.mjs";
import { createProjectWorkerAgent } from "./novel_worker_agent.mjs";

export const NOVEL_TOOL_NAMES = Object.freeze([
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

function createClosedResourceLoader(resourcesDir, projectRoot) {
  const projectOverride = path.join(projectRoot, ".awp", "prompts", "editor.md");
  const systemPrompt = fs.readFileSync(
    fs.existsSync(projectOverride)
      ? projectOverride
      : path.join(resourcesDir, "system-prompt.md"),
    "utf8",
  );
  const skillsDir = path.join(resourcesDir, "skills");
  const skills = fs.readdirSync(skillsDir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => {
      const filePath = path.join(skillsDir, entry.name, "SKILL.md");
      return {
        name: entry.name,
        description: fs.readFileSync(filePath, "utf8").split("\n").find((line) => line.startsWith("description:"))?.replace("description:", "").trim() ?? entry.name,
        filePath,
        baseDir: path.dirname(filePath),
        sourceInfo: createSyntheticSourceInfo(filePath, { source: "awp-novel-harness" }),
        disableModelInvocation: false,
      };
    });

  return {
    getExtensions: () => ({ extensions: [], errors: [], runtime: createExtensionRuntime() }),
    getSkills: () => ({ skills, diagnostics: [] }),
    getPrompts: () => ({ prompts: [], diagnostics: [] }),
    getThemes: () => ({ themes: [], diagnostics: [] }),
    getAgentsFiles: () => ({ agentsFiles: [] }),
    getSystemPrompt: () => systemPrompt,
    getAppendSystemPrompt: () => [],
    extendResources: () => {},
    reload: async () => {},
  };
}

export async function createNovelAgentSession(
  initPayload,
  requestPython,
  resourcesDir,
  { createSession = createAgentSession } = {},
) {
  const connection = initPayload.connection;
  const authStorage = AuthStorage.inMemory();
  const modelRegistry = ModelRegistry.inMemory(authStorage);
  modelRegistry.registerProvider(connection.provider, {
    name: connection.provider,
    baseUrl: connection.base_url,
    apiKey: `$${connection.api_key_env}`,
    api: "openai-completions",
    authHeader: true,
    models: [{
      id: connection.model,
      name: connection.model,
      reasoning: true,
      input: ["text"],
      cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
      contextWindow: 131072,
      maxTokens: 4000,
    }],
  });
  const model = modelRegistry.find(connection.provider, connection.model);
  if (!model) {
    throw new Error(`Pi model was not registered: ${connection.provider}/${connection.model}`);
  }

  let workerActive = false;
  const delegateProjectTask = async (args) => {
    if (workerActive) throw new Error("a project worker is already active");
    workerActive = true;
    try {
      const worker = await createProjectWorkerAgent(
        initPayload,
        requestPython,
      );
      return await worker.run(args);
    } finally {
      workerActive = false;
    }
  };

  return createSession({
    cwd: initPayload.project_root,
    agentDir: initPayload.session_dir,
    model,
    thinkingLevel: connection.thinking_level ?? "low",
    authStorage,
    modelRegistry,
    settingsManager: SettingsManager.inMemory(),
    sessionManager: SessionManager.continueRecent(initPayload.project_root, initPayload.session_dir),
    resourceLoader: createClosedResourceLoader(resourcesDir, initPayload.project_root),
    noTools: "all",
    tools: NOVEL_TOOL_NAMES,
    customTools: createNovelTools(requestPython, { delegateProjectTask }),
  });
}

export class NovelAgentHost {
  constructor({
    createSession = createNovelAgentSession,
    writeFrame = () => {},
    resourcesDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "resources"),
  } = {}) {
    this._createSession = createSession;
    this._writeFrame = writeFrame;
    this._resourcesDir = resourcesDir;
    this._session = undefined;
    this._activeRequestId = undefined;
    this._pendingTools = new Map();
  }

  async handleFrame(frame) {
    if (frame.kind === "init") {
      await this._initialize(frame);
      return;
    }
    if (frame.kind === "prompt") {
      this._startPrompt(frame);
      return;
    }
    if (frame.kind === "cancel") {
      await this._cancel(frame);
      return;
    }
    if (frame.kind === "tool_result") {
      this._resolveTool(frame);
      return;
    }
    if (frame.kind === "shutdown") {
      this._session?.dispose();
      return;
    }
    this._error(frame.request_id, `unsupported host frame: ${frame.kind}`);
  }

  async _initialize(frame) {
    if (this._session) this._session.dispose();
    const created = await this._createSession(
      frame.payload,
      (name, arguments_, signal) => {
        if (!this._activeRequestId) {
          return Promise.reject(new Error("Pi tool call has no active editor prompt"));
        }
        return this._requestPython(this._activeRequestId, name, arguments_, signal);
      },
      this._resourcesDir,
    );
    this._session = created.session;
    this._session.subscribe((event) => {
      if (event.type === "message_update" && event.assistantMessageEvent.type === "text_delta") {
        this._emit(this._activeRequestId, "assistant_delta", { text: event.assistantMessageEvent.delta });
      }
    });
    this._writeFrame({ kind: "event", request_id: frame.request_id, payload: { type: "ready" } });
  }

  _startPrompt(frame) {
    if (!this._session) {
      this._error(frame.request_id, "Pi session is not initialized");
      return;
    }
    if (this._activeRequestId) {
      this._error(frame.request_id, "Pi session already has an active prompt");
      return;
    }
    this._activeRequestId = frame.request_id;
    void this._session.prompt(String(frame.payload.text ?? ""))
      .then(() => this._writeFrame({ kind: "turn_end", request_id: frame.request_id, payload: { text: this._session.getLastAssistantText() ?? "" } }))
      .catch((error) => this._error(frame.request_id, error instanceof Error ? error.message : String(error)))
      .finally(() => { this._activeRequestId = undefined; });
  }

  async _cancel(frame) {
    if (!this._session || frame.request_id !== this._activeRequestId) {
      this._error(frame.request_id, "no active Pi prompt to cancel");
      return;
    }
    await this._session.abort();
    this._writeFrame({ kind: "event", request_id: frame.request_id, payload: { type: "cancelled" } });
  }

  _requestPython(requestId, name, arguments_, signal) {
    const toolCallId = randomUUID();
    return new Promise((resolve, reject) => {
      this._pendingTools.set(toolCallId, { resolve, reject });
      signal?.addEventListener("abort", () => {
        this._pendingTools.delete(toolCallId);
        reject(new Error("Pi tool call cancelled"));
      }, { once: true });
      this._writeFrame({ kind: "tool_call", request_id: requestId, payload: { tool_call_id: toolCallId, name, arguments: arguments_ } });
    });
  }

  _resolveTool(frame) {
    const toolCallId = String(frame.payload.tool_call_id ?? "");
    const pending = this._pendingTools.get(toolCallId);
    if (!pending) {
      this._error(frame.request_id, `unknown Pi tool call: ${toolCallId}`);
      return;
    }
    this._pendingTools.delete(toolCallId);
    if (frame.payload.ok) pending.resolve({ content: String(frame.payload.content ?? "") });
    else pending.reject(new Error(String(frame.payload.content ?? "Python tool failed")));
  }

  _emit(requestId, type, payload) {
    if (requestId) this._writeFrame({ kind: "event", request_id: requestId, payload: { type, ...payload } });
  }

  _error(requestId, message) {
    this._writeFrame({ kind: "error", request_id: requestId, payload: { message } });
  }
}

function writeLine(frame) {
  process.stdout.write(`${JSON.stringify(frame)}\n`);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const host = new NovelAgentHost({ writeFrame: writeLine });
  const input = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
  input.on("line", (line) => {
    try {
      const frame = JSON.parse(line);
      void host.handleFrame(frame);
    } catch (error) {
      writeLine({ kind: "error", request_id: "protocol", payload: { message: error instanceof Error ? error.message : String(error) } });
    }
  });
}
