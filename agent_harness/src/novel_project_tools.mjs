import { defineTool } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";


const strict = { additionalProperties: false };
const pathText = Type.String({ minLength: 1, maxLength: 2000 });
const positiveLimit = Type.Integer({ minimum: 1, maximum: 2000 });
const hash = Type.String({ pattern: "^[0-9a-f]{64}$" });


function rpcTool(requestPython, name, description, parameters) {
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


export function createNovelProjectTools(requestPython) {
  return [
    rpcTool(
      requestPython,
      "read",
      "读取当前小说项目内的 UTF-8 文本，可指定起始行和行数。",
      Type.Object({
        path: pathText,
        offset: Type.Optional(Type.Integer({ minimum: 1 })),
        limit: Type.Optional(positiveLimit),
      }, strict),
    ),
    rpcTool(
      requestPython,
      "ls",
      "列出当前小说项目内的目录内容。",
      Type.Object({
        path: Type.Optional(pathText),
        limit: Type.Optional(positiveLimit),
      }, strict),
    ),
    rpcTool(
      requestPython,
      "find",
      "按文件名或相对路径通配符查找当前小说项目文件。",
      Type.Object({
        pattern: Type.String({ minLength: 1, maxLength: 500 }),
        path: Type.Optional(pathText),
        limit: Type.Optional(positiveLimit),
      }, strict),
    ),
    rpcTool(
      requestPython,
      "grep",
      "在当前小说项目文本中搜索内容，结果包含相对路径和行号。",
      Type.Object({
        pattern: Type.String({ minLength: 1, maxLength: 1000 }),
        path: Type.Optional(pathText),
        glob: Type.Optional(Type.String({ minLength: 1, maxLength: 500 })),
        ignoreCase: Type.Optional(Type.Boolean()),
        literal: Type.Optional(Type.Boolean()),
        context: Type.Optional(Type.Integer({ minimum: 0, maximum: 20 })),
        limit: Type.Optional(positiveLimit),
      }, strict),
    ),
    rpcTool(
      requestPython,
      "write",
      "新建或完整写入当前小说项目文本；重要文件会等待作者审批。",
      Type.Object({
        path: pathText,
        content: Type.String({ maxLength: 2 * 1024 * 1024 }),
        expected_hash: Type.Optional(hash),
      }, strict),
    ),
    rpcTool(
      requestPython,
      "edit",
      "用唯一的精确文本匹配局部修改小说项目文件，并保留旧版本。",
      Type.Object({
        path: pathText,
        edits: Type.Array(
          Type.Object({
            oldText: Type.String({ minLength: 1 }),
            newText: Type.String(),
          }, strict),
          { minItems: 1, maxItems: 100 },
        ),
        expected_hash: Type.Optional(hash),
      }, strict),
    ),
    rpcTool(
      requestPython,
      "bash",
      "执行沙箱能静态证明安全的项目辅助命令；不明、网络或系统命令会被拒绝。",
      Type.Object({
        command: Type.String({ minLength: 1, maxLength: 4000 }),
        timeout: Type.Optional(Type.Integer({ minimum: 1, maximum: 30 })),
      }, strict),
    ),
  ];
}
