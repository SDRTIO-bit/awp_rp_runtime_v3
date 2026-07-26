import fs from "node:fs";
import path from "node:path";

import {
  createExtensionRuntime,
  createSyntheticSourceInfo,
} from "@earendil-works/pi-coding-agent";

import { ROLE_TOOL_ALLOWLISTS } from "./novel_role_tools.mjs";


function frontmatterValue(text, key, fallback) {
  const prefix = `${key}:`;
  const line = text.split(/\r?\n/).find((candidate) => candidate.trim().startsWith(prefix));
  return line ? line.trim().slice(prefix.length).trim() || fallback : fallback;
}

function loadSkills(skillsDir, source) {
  if (!fs.existsSync(skillsDir)) return [];
  return fs.readdirSync(skillsDir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .flatMap((entry) => {
      const filePath = path.join(skillsDir, entry.name, "SKILL.md");
      if (!fs.existsSync(filePath)) return [];
      const text = fs.readFileSync(filePath, "utf8");
      return [{
        name: frontmatterValue(text, "name", entry.name),
        description: frontmatterValue(text, "description", entry.name),
        filePath,
        baseDir: path.dirname(filePath),
        sourceInfo: createSyntheticSourceInfo(filePath, { source }),
        disableModelInvocation: false,
      }];
    });
}

export function createRoleResourceLoader(role, resourcesRoot, projectRoot) {
  if (!ROLE_TOOL_ALLOWLISTS[role]) {
    throw new Error(`unsupported Pi novel role: ${role}`);
  }
  const roleRoot = path.join(resourcesRoot, role);
  const systemPromptPath = path.join(roleRoot, "system-prompt.md");
  if (!fs.existsSync(systemPromptPath)) {
    throw new Error(`missing Pi role system prompt: ${role}`);
  }
  const projectOverride = path.join(projectRoot, ".awp", "prompts", `${role}.md`);
  const systemPrompt = fs.readFileSync(
    fs.existsSync(projectOverride) ? projectOverride : systemPromptPath,
    "utf8",
  );
  const builtInSkills = loadSkills(path.join(roleRoot, "skills"), `awp-role:${role}`);
  const projectSkills = loadSkills(
    path.join(projectRoot, "agent", "skills"),
    "awp-novel-project",
  );
  const skills = [...builtInSkills, ...projectSkills];

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

