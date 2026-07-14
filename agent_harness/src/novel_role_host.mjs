import path from "node:path";
import readline from "node:readline";
import { createHash, randomUUID } from "node:crypto";
import { fileURLToPath } from "node:url";

import {
  AuthStorage,
  createAgentSession,
  ModelRegistry,
  SessionManager,
  SettingsManager,
} from "@earendil-works/pi-coding-agent";

import { createRoleResourceLoader } from "./novel_role_resources.mjs";
import { createRoleTools, ROLE_TOOL_ALLOWLISTS } from "./novel_role_tools.mjs";


function requireString(value, label) {
  if (typeof value !== "string" || value.trim() === "") {
    throw new Error(`${label} must be a non-empty string`);
  }
  return value;
}

function sessionDirectory(sessionRoot, sessionKey) {
  const digest = createHash("sha256").update(sessionKey).digest("hex").slice(0, 24);
  return path.join(sessionRoot, digest);
}

function normalizeThinkingLevel(value) {
  if (["disabled", "none"].includes(value)) return "off";
  if (["off", "minimal", "low", "medium", "high", "xhigh", "max"].includes(value)) {
    return value;
  }
  return "low";
}

function buildRolePrompt(task) {
  return [
    "请执行下面的小说角色任务。你可以自主决定是否调用已授权的只读工具。",
    "先完成任务，再做一次整体检查；不要逐条复述契约，不要为缺失的非关键背景反复推断。若信息不足，采用最小合理假设继续。",
    "",
    `角色：${task.role}`,
    `阶段：${task.phase ?? ""}`,
    `章节：${task.chapter_index}`,
    `修订：${task.revision}`,
    "",
    "任务契约：",
    String(task.task_contract ?? ""),
    "",
    "任务输入（JSON）：",
    JSON.stringify(task.input_payload ?? {}, null, 2),
  ].join("\n");
}

function normalizeUsage(session) {
  const tokens = session.getSessionStats?.().tokens ?? {};
  return {
    input: Number(tokens.input ?? 0),
    output: Number(tokens.output ?? 0),
    cache_read: Number(tokens.cacheRead ?? 0),
    cache_write: Number(tokens.cacheWrite ?? 0),
    total: Number(tokens.total ?? 0),
  };
}

function parseStructuredData(text) {
  try {
    const parsed = JSON.parse(text);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

export async function createNovelRoleSession(
  task,
  runtime,
  requestPython,
  resourcesRoot,
  { createSession = createAgentSession } = {},
) {
  const role = requireString(task.role, "role");
  const allowedTools = ROLE_TOOL_ALLOWLISTS[role];
  if (!allowedTools) throw new Error(`unsupported Pi novel role: ${role}`);

  const connection = task.connection ?? task.model_connection;
  if (!connection) throw new Error(`missing model connection for Pi role: ${role}`);
  const provider = requireString(connection.provider, "connection.provider");
  const modelId = requireString(connection.model, "connection.model");
  const authStorage = AuthStorage.inMemory();
  const modelRegistry = ModelRegistry.inMemory(authStorage);
  const thinkingLevel = normalizeThinkingLevel(task.thinking_level);
  modelRegistry.registerProvider(provider, {
    name: provider,
    baseUrl: requireString(connection.base_url, "connection.base_url"),
    apiKey: `$${requireString(connection.api_key_env, "connection.api_key_env")}`,
    api: connection.api ?? "openai-completions",
    authHeader: connection.auth_header ?? true,
    models: [{
      id: modelId,
      name: modelId,
      reasoning: thinkingLevel !== "off",
      input: ["text"],
      cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
      contextWindow: Number(connection.context_window ?? 131072),
      maxTokens: Number(task.max_tokens ?? 4000),
    }],
  });
  const model = modelRegistry.find(provider, modelId);
  if (!model) throw new Error(`Pi role model was not registered: ${provider}/${modelId}`);

  const projectRoot = requireString(runtime.project_root, "project_root");
  const sessionDir = requireString(runtime.session_dir, "session_dir");
  return createSession({
    cwd: projectRoot,
    agentDir: sessionDir,
    model,
    thinkingLevel,
    authStorage,
    modelRegistry,
    settingsManager: SettingsManager.inMemory(),
    sessionManager: SessionManager.create(projectRoot, sessionDir),
    resourceLoader: createRoleResourceLoader(role, resourcesRoot, projectRoot),
    noTools: "all",
    tools: [...allowedTools],
    customTools: createRoleTools(role, requestPython),
  });
}

export class NovelRoleHost {
  constructor({
    createSession = createNovelRoleSession,
    writeFrame = () => {},
    resourcesRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "resources", "roles"),
  } = {}) {
    this._createSession = createSession;
    this._writeFrame = writeFrame;
    this._resourcesRoot = resourcesRoot;
    this._binding = undefined;
    this._sessions = new Map();
    this._active = new Map();
    this._pendingTools = new Map();
  }

  async handleFrame(frame) {
    try {
      if (frame.kind === "role_init") return await this._initialize(frame);
      if (frame.kind === "role_prompt") return await this._startRole(frame);
      if (frame.kind === "tool_result") return this._resolveTool(frame);
      if (frame.kind === "cancel") return await this._cancel(frame);
      if (frame.kind === "close_session") return this._closeSession(frame);
      if (frame.kind === "shutdown") return this._shutdown(frame);
      return this._error(frame.request_id, `unsupported role frame: ${frame.kind}`);
    } catch (error) {
      return this._error(frame.request_id, error instanceof Error ? error.message : String(error));
    }
  }

  async _initialize(frame) {
    await this._disposeAll();
    const payload = frame.payload ?? {};
    this._binding = {
      project_id: requireString(payload.project_id, "project_id"),
      project_root: requireString(payload.project_root, "project_root"),
      session_root: requireString(payload.session_root, "session_root"),
    };
    this._writeFrame({
      kind: "event",
      request_id: frame.request_id,
      payload: { type: "ready", runtime: "pi-role-agent" },
    });
  }

  async _startRole(frame) {
    if (!this._binding) throw new Error("Pi role host is not initialized");
    const task = frame.payload ?? {};
    const sessionKey = requireString(task.session_key, "session_key");
    const role = requireString(task.role, "role");
    if (!ROLE_TOOL_ALLOWLISTS[role]) throw new Error(`unsupported Pi novel role: ${role}`);
    if (task.project_id !== this._binding.project_id) {
      throw new Error("Pi role task belongs to a different project");
    }

    let entry = this._sessions.get(sessionKey);
    if (entry && entry.role !== role) {
      throw new Error(`Pi role session key is already bound to ${entry.role}`);
    }
    if (entry?.activeRequestId) {
      throw new Error(`Pi role session is busy: ${sessionKey}`);
    }
    if (!entry) {
      const activity = { requestId: frame.request_id, stream: Boolean(task.stream) };
      const runtime = {
        project_root: this._binding.project_root,
        session_dir: sessionDirectory(this._binding.session_root, sessionKey),
      };
      const created = await this._createSession(
        task,
        runtime,
        (name, arguments_, signal) => this._requestPython(activity.requestId, name, arguments_, signal),
        this._resourcesRoot,
      );
      entry = {
        session: created.session,
        role,
        sessionKey,
        activity,
        activeRequestId: undefined,
        cancelled: false,
      };
      entry.session.subscribe((event) => {
        if (
          entry.activity.stream
          && event.type === "message_update"
          && event.assistantMessageEvent?.type === "text_delta"
        ) {
          this._emit(entry.activity.requestId, "text_delta", {
            text: event.assistantMessageEvent.delta,
            role: entry.role,
            session_key: entry.sessionKey,
          });
        }
      });
      this._sessions.set(sessionKey, entry);
    }

    entry.activity.requestId = frame.request_id;
    entry.activity.stream = Boolean(task.stream);
    entry.activeRequestId = frame.request_id;
    entry.cancelled = false;
    this._active.set(frame.request_id, entry);
    const startedAt = Date.now();
    this._emit(frame.request_id, "role_started", { role, session_key: sessionKey });

    try {
      await entry.session.prompt(buildRolePrompt(task));
      if (entry.cancelled) return;
      const text = entry.session.getLastAssistantText?.() ?? "";
      this._writeFrame({
        kind: "role_end",
        request_id: frame.request_id,
        payload: {
          request_id: frame.request_id,
          role,
          session_key: sessionKey,
          text,
          structured_data: parseStructuredData(text),
          model: entry.session.model?.id ?? task.connection?.model ?? task.model_connection?.model ?? "",
          usage: normalizeUsage(entry.session),
          finish_reason: "stop",
          latency_ms: Math.max(0, Date.now() - startedAt),
        },
      });
      if (role !== "writer") this._disposeEntry(entry);
    } catch (error) {
      this._disposeEntry(entry);
      if (!entry.cancelled) {
        this._error(frame.request_id, error instanceof Error ? error.message : String(error));
      }
    } finally {
      this._active.delete(frame.request_id);
      entry.activeRequestId = undefined;
    }
  }

  async _cancel(frame) {
    const entry = this._active.get(frame.request_id);
    if (!entry) throw new Error("no active Pi role prompt to cancel");
    entry.cancelled = true;
    await entry.session.abort();
    this._disposeEntry(entry);
    this._active.delete(frame.request_id);
    this._emit(frame.request_id, "cancelled", {
      role: entry.role,
      session_key: entry.sessionKey,
    });
  }

  _closeSession(frame) {
    const sessionKey = requireString(frame.payload?.session_key, "session_key");
    const entry = this._sessions.get(sessionKey);
    if (!entry) {
      this._emit(frame.request_id, "session_closed", { session_key: sessionKey, existed: false });
      return;
    }
    if (entry.activeRequestId) throw new Error(`cannot close active Pi role session: ${sessionKey}`);
    this._disposeEntry(entry);
    this._emit(frame.request_id, "session_closed", { session_key: sessionKey, existed: true });
  }

  _requestPython(requestId, name, arguments_, signal) {
    const toolCallId = randomUUID();
    return new Promise((resolve, reject) => {
      this._pendingTools.set(toolCallId, { resolve, reject, requestId });
      signal?.addEventListener("abort", () => {
        this._pendingTools.delete(toolCallId);
        reject(new Error("Pi role tool call cancelled"));
      }, { once: true });
      this._writeFrame({
        kind: "tool_call",
        request_id: requestId,
        payload: { tool_call_id: toolCallId, name, arguments: arguments_ },
      });
    });
  }

  _resolveTool(frame) {
    const toolCallId = String(frame.payload?.tool_call_id ?? "");
    const pending = this._pendingTools.get(toolCallId);
    if (!pending) throw new Error(`unknown Pi role tool call: ${toolCallId}`);
    if (pending.requestId !== frame.request_id) {
      throw new Error(`Pi role tool result request mismatch: ${toolCallId}`);
    }
    this._pendingTools.delete(toolCallId);
    if (frame.payload.ok) pending.resolve({ content: String(frame.payload.content ?? "") });
    else pending.reject(new Error(String(frame.payload.content ?? "Python read tool failed")));
  }

  _disposeEntry(entry) {
    if (entry.disposed) return;
    entry.disposed = true;
    if (this._sessions.get(entry.sessionKey) === entry) this._sessions.delete(entry.sessionKey);
    entry.session.dispose();
  }

  async _disposeAll() {
    for (const entry of this._sessions.values()) {
      if (entry.activeRequestId) {
        entry.cancelled = true;
        await entry.session.abort();
      }
      entry.session.dispose();
    }
    this._sessions.clear();
    this._active.clear();
    for (const pending of this._pendingTools.values()) {
      pending.reject(new Error("Pi role host closed"));
    }
    this._pendingTools.clear();
  }

  async _shutdown(frame) {
    await this._disposeAll();
    this._binding = undefined;
    this._emit(frame.request_id, "shutdown", {});
  }

  _emit(requestId, type, payload) {
    this._writeFrame({ kind: "event", request_id: requestId, payload: { type, ...payload } });
  }

  _error(requestId, message) {
    this._writeFrame({ kind: "error", request_id: requestId, payload: { message } });
  }
}

function writeLine(frame) {
  process.stdout.write(`${JSON.stringify(frame)}\n`);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const host = new NovelRoleHost({ writeFrame: writeLine });
  const input = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
  input.on("line", (line) => {
    try {
      void host.handleFrame(JSON.parse(line));
    } catch (error) {
      writeLine({
        kind: "error",
        request_id: "protocol",
        payload: { message: error instanceof Error ? error.message : String(error) },
      });
    }
  });
}
