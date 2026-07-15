import { defineTool } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";


export const ROLE_TOOL_ALLOWLISTS = Object.freeze({
  architect: Object.freeze([
    "project_status",
    "read_project_contract",
    "read_chapter",
    "read_ledger",
    "read_characters",
  ]),
  director: Object.freeze([
    "read_project_contract",
    "read_chapter_plan",
    "read_chapter",
    "read_ledger",
    "read_characters",
  ]),
  writer: Object.freeze([
    "read_chapter_plan",
    "read_chapter",
    "read_ledger",
    "read_characters",
    "read_write_packet",
  ]),
  continuity_checker: Object.freeze([
    "read_chapter_plan",
    "read_chapter",
    "read_ledger",
    "read_characters",
  ]),
  style_cleaner: Object.freeze([]),
  ledger_curator: Object.freeze([
    "read_chapter_plan",
    "read_chapter",
    "read_ledger",
    "read_characters",
  ]),
});

const TOOL_DEFINITIONS = Object.freeze({
  project_status: {
    description: "读取当前绑定小说项目和活动章节的状态。",
    parameters: Type.Object({}),
  },
  read_project_contract: {
    description: "读取当前绑定项目和卷的结构化契约。",
    parameters: Type.Object({}),
  },
  read_chapter_plan: {
    description: "读取当前项目指定章节的计划。",
    parameters: Type.Object({
      chapter_index: Type.Optional(Type.Integer({ minimum: 1, maximum: 100000 })),
    }),
  },
  read_chapter: {
    description: "读取当前项目指定章节的已提交正文。",
    parameters: Type.Object({
      chapter_index: Type.Optional(Type.Integer({ minimum: 1, maximum: 100000 })),
    }),
  },
  read_ledger: {
    description: "读取当前项目的连续性账本。",
    parameters: Type.Object({
      section: Type.Optional(Type.String({ maxLength: 80 })),
      limit: Type.Optional(Type.Integer({ minimum: 1, maximum: 200 })),
    }),
  },
  read_characters: {
    description: "读取当前项目的角色状态和关系。",
    parameters: Type.Object({
      limit: Type.Optional(Type.Integer({ minimum: 1, maximum: 100 })),
    }),
  },
  read_write_packet: {
    description: "读取当前 Writer 任务绑定的写作包。",
    parameters: Type.Object({}),
  },
});

function createRpcTool(requestPython, name) {
  const definition = TOOL_DEFINITIONS[name];
  return defineTool({
    name,
    label: name,
    description: definition.description,
    parameters: definition.parameters,
    executionMode: "sequential",
    async execute(_toolCallId, params, signal) {
      const result = await requestPython(name, params, signal);
      return {
        content: [{ type: "text", text: String(result.content ?? "") }],
      };
    },
  });
}

export function createRoleTools(role, requestPython) {
  const names = ROLE_TOOL_ALLOWLISTS[role];
  if (!names) throw new Error(`unsupported Pi novel role: ${role}`);
  return names.map((name) => createRpcTool(requestPython, name));
}

