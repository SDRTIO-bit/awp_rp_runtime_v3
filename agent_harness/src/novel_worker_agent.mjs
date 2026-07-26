import path from "node:path";
import { randomUUID } from "node:crypto";

import {
  AuthStorage,
  createAgentSession,
  createExtensionRuntime,
  ModelRegistry,
  SessionManager,
  SettingsManager,
} from "@earendil-works/pi-coding-agent";

import { createNovelProjectTools } from "./novel_project_tools.mjs";


const READ_ONLY_TOOLS = Object.freeze(["read", "ls", "find", "grep"]);
const WORKER_SYSTEM_PROMPT = `你是小说项目的只读资料核对员。
只根据当前小说项目内的文件回答委派问题。
必须使用相对路径和行号给出证据，例如 world.md:12。
不得创作或决定剧情，不得猜测没有证据的事实，不得修改文件、执行终端、批准计划、启动写作管线或创建其他 Agent。
证据不足时明确列出缺失信息。`;


function createWorkerResourceLoader() {
  return {
    getExtensions: () => ({ extensions: [], errors: [], runtime: createExtensionRuntime() }),
    getSkills: () => ({ skills: [], diagnostics: [] }),
    getPrompts: () => ({ prompts: [], diagnostics: [] }),
    getThemes: () => ({ themes: [], diagnostics: [] }),
    getAgentsFiles: () => ({ agentsFiles: [] }),
    getSystemPrompt: () => WORKER_SYSTEM_PROMPT,
    getAppendSystemPrompt: () => [],
    extendResources: () => {},
    reload: async () => {},
  };
}


function validateTask(args) {
  const task = String(args?.task ?? "").trim();
  if (!task || task.length > 8000) {
    throw new Error("worker task must contain 1-8000 characters");
  }
  const focusPaths = args?.focus_paths ?? [];
  if (!Array.isArray(focusPaths) || focusPaths.length > 20) {
    throw new Error("worker focus_paths must contain at most 20 paths");
  }
  for (const raw of focusPaths) {
    const value = String(raw ?? "").replaceAll("\\", "/");
    if (!value || path.isAbsolute(value) || value.split("/").includes("..")) {
      throw new Error("worker focus paths must be project-relative");
    }
  }
  const maxFiles = Number(args?.max_files ?? 50);
  if (!Number.isInteger(maxFiles) || maxFiles < 1 || maxFiles > 100) {
    throw new Error("worker max_files must be between 1 and 100");
  }
  return { task, focusPaths, maxFiles };
}


export async function createProjectWorkerAgent(
  initPayload,
  requestPython,
  {
    createSession = createAgentSession,
    timeoutMs = 180000,
    createSessionManager = (projectRoot, workerDir) => (
      SessionManager.continueRecent(projectRoot, workerDir)
    ),
  } = {},
) {
  let active = false;
  return {
    async run(args) {
      if (active) throw new Error("a project worker is already active");
      const { task, focusPaths, maxFiles } = validateTask(args);
      active = true;
      let session;
      let timer;
      try {
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
            maxTokens: 2500,
          }],
        });
        const model = modelRegistry.find(connection.provider, connection.model);
        if (!model) throw new Error("worker Pi model was not registered");
        const workerDir = path.join(
          initPayload.project_root,
          ".awp",
          "pi-sessions",
          "workers",
          randomUUID(),
        );
        const readTools = createNovelProjectTools(requestPython)
          .filter((tool) => READ_ONLY_TOOLS.includes(tool.name));
        const created = await createSession({
          cwd: initPayload.project_root,
          agentDir: workerDir,
          model,
          thinkingLevel: connection.thinking_level ?? "low",
          authStorage,
          modelRegistry,
          settingsManager: SettingsManager.inMemory(),
          sessionManager: createSessionManager(
            initPayload.project_root,
            workerDir,
          ),
          resourceLoader: createWorkerResourceLoader(),
          noTools: "all",
          tools: [...READ_ONLY_TOOLS],
          customTools: readTools,
        });
        session = created.session;
        const focus = focusPaths.length
          ? `\n优先检查：${focusPaths.join("、")}`
          : "";
        const prompt = `委派任务：${task}${focus}\n最多检查 ${maxFiles} 个文件。只返回带相对路径和行号的证据摘要。`;
        await Promise.race([
          session.prompt(prompt),
          new Promise((_, reject) => {
            timer = setTimeout(
              () => reject(new Error("project worker timed out")),
              timeoutMs,
            );
          }),
        ]);
        return session.getLastAssistantText() ?? "Worker 未返回证据。";
      } finally {
        if (timer) clearTimeout(timer);
        session?.dispose();
        active = false;
      }
    },
  };
}


export { READ_ONLY_TOOLS };
