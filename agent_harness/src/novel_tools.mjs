import { defineTool } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

const chapterParameters = Type.Object({
  chapter: Type.Integer({ minimum: 1, maximum: 100000 }),
});

const planParameters = Type.Intersect([
  chapterParameters,
  Type.Object({
    task_description: Type.Optional(Type.String({ maxLength: 2000 })),
  }),
]);

const writeParameters = Type.Intersect([
  chapterParameters,
  Type.Object({
    write_guidance: Type.Optional(Type.String({ maxLength: 2000 })),
  }),
]);

function createRpcTool(requestPython, name, description, parameters) {
  return defineTool({
    name,
    label: name,
    description,
    parameters,
    executionMode: "sequential",
    async execute(_toolCallId, params, signal) {
      const result = await requestPython(name, params, signal);
      return {
        content: [{ type: "text", text: String(result.content ?? "") }],
      };
    },
  });
}

export function createNovelTools(requestPython) {
  return [
    createRpcTool(requestPython, "project_status", "读取当前小说项目的状态。", Type.Object({})),
    createRpcTool(requestPython, "read_chapter", "读取当前项目中已生成的一章。", chapterParameters),
    createRpcTool(requestPython, "plan_chapter", "为当前项目规划一章。", planParameters),
    createRpcTool(requestPython, "write_chapter", "生成当前项目中已规划的一章。", writeParameters),
    createRpcTool(requestPython, "audit_chapter", "只读审计当前项目中已生成的一章。", chapterParameters),
  ];
}
