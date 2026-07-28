import { defineTool } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

import { createNovelProjectTools } from "./novel_project_tools.mjs";

const strict = { additionalProperties: false };
const shortText = Type.String({ minLength: 1, maxLength: 4000 });
const textList = Type.Array(shortText, { maxItems: 100 });
const chapterParameters = Type.Object({
  chapter: Type.Integer({ minimum: 1, maximum: 100000 }),
}, strict);

const sceneParameters = Type.Object({
  scene_id: Type.String({ minLength: 1, maxLength: 100 }),
  summary: shortText,
  change: shortText,
  opening_state: Type.Optional(shortText),
  ending_state: Type.Optional(shortText),
  purpose: Type.Optional(shortText),
  characters: Type.Optional(textList),
}, strict);

const characterIntentParameters = Type.Object({
  character: Type.String({ minLength: 1, maxLength: 200 }),
  goal: Type.Optional(shortText),
  motivation: Type.Optional(shortText),
  choice: Type.Optional(shortText),
  subtext: Type.Optional(shortText),
  boundaries: Type.Optional(textList),
  new_character: Type.Optional(Type.Boolean()),
}, strict);

const savePlanParameters = Type.Object({
  plan_id: Type.Optional(Type.String({ minLength: 1, maxLength: 200 })),
  chapter_index: Type.Integer({ minimum: 1, maximum: 100000 }),
  title: Type.Optional(Type.String({ maxLength: 500 })),
  target_chars: Type.Optional(Type.Integer({ minimum: 1, maximum: 100000 })),
  purpose: shortText,
  target_reader_effect: Type.Optional(shortText),
  confirmed_events: Type.Array(shortText, { minItems: 1, maxItems: 100 }),
  causal_chain: Type.Optional(textList),
  scenes: Type.Array(sceneParameters, { minItems: 1, maxItems: 100 }),
  character_intents: Type.Optional(Type.Array(characterIntentParameters, { maxItems: 100 })),
  world_constraints: Type.Optional(textList),
  information_distribution: Type.Optional(textList),
  must_keep: Type.Optional(textList),
  must_not: Type.Optional(textList),
  deliberate_ambiguities: Type.Optional(textList),
  writer_freedom: Type.Optional(textList),
  unresolved_questions: Type.Optional(textList),
  source_material_ids: Type.Optional(textList),
}, strict);

const planActionParameters = Type.Object({
  plan_id: Type.String({ minLength: 1, maxLength: 200 }),
  revision: Type.Integer({ minimum: 1 }),
  confirmation_quote: Type.String({ minLength: 1, maxLength: 500 }),
}, strict);

const revisionPatchParameters = Type.Object({
  patch_id: Type.String({ minLength: 1, maxLength: 100 }),
  paragraph_id: Type.String({ minLength: 1, maxLength: 100 }),
  expected_paragraph_hash: Type.String({ pattern: "^[0-9a-f]{64}$" }),
  operation: Type.Union([
    Type.Literal("replace"), Type.Literal("delete"),
    Type.Literal("insert_before"), Type.Literal("insert_after"),
  ]),
  replacement_text: Type.String({ maxLength: 100000 }),
  reason: shortText,
  narrative_impact: Type.Optional(Type.String({ maxLength: 2000 })),
  downstream_impact: Type.Optional(Type.String({ maxLength: 2000 })),
}, strict);

const saveRevisionPlanParameters = Type.Object({
  plan_id: Type.Optional(Type.String({ minLength: 1, maxLength: 100 })),
  chapter_index: Type.Integer({ minimum: 1, maximum: 100000 }),
  base_revision: Type.Integer({ minimum: 1 }),
  patches: Type.Array(revisionPatchParameters, { minItems: 1, maxItems: 100 }),
  reason: Type.Optional(Type.String({ maxLength: 2000 })),
}, strict);

const revisionActionParameters = Type.Object({
  plan_id: Type.String({ minLength: 1, maxLength: 100 }),
  confirmation_quote: Type.String({ minLength: 1, maxLength: 500 }),
}, strict);

const applyRevisionPlanParameters = Type.Object({
  ...revisionActionParameters.properties,
  expected_revision: Type.Integer({ minimum: 1 }),
}, strict);

const proposeProjectSkillParameters = Type.Object({
  proposal_id: Type.Optional(Type.String({ minLength: 1, maxLength: 100 })),
  skill_id: Type.String({ pattern: "^[a-z0-9-]{1,64}$" }),
  content: Type.String({ minLength: 1, maxLength: 32768 }),
  purpose: shortText,
  behavior_impact: shortText,
}, strict);

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

const workPlanItem = Type.Object({
  description: shortText,
  status: Type.Optional(Type.String({ minLength: 1, maxLength: 50 })),
}, strict);

const workPlanParameters = Type.Object({
  explanation: Type.Optional(Type.String({ maxLength: 2000 })),
  items: Type.Array(workPlanItem, { minItems: 1, maxItems: 50 }),
}, strict);

export function createNovelTools(requestPython, options = {}) {
  return [
    ...createNovelProjectTools(requestPython, options),
    createRpcTool(requestPython, "project_status", "读取当前小说项目状态。", Type.Object({}, strict)),
    createRpcTool(requestPython, "read_chapter", "读取当前项目中已生成的一章。", chapterParameters),
    createRpcTool(
      requestPython,
      "save_revision_plan",
      "保存等待作者确认的既有正文修订计划；不能代替作者批准。",
      saveRevisionPlanParameters,
    ),
    createRpcTool(
      requestPython,
      "approve_revision_plan",
      "依据当前作者消息批准既有正文修订计划；只批准，不应用。",
      revisionActionParameters,
    ),
    createRpcTool(
      requestPython,
      "apply_revision_plan",
      "依据批准之后的新一轮作者指令，将正文修订应用为新版本。",
      applyRevisionPlanParameters,
    ),
    createRpcTool(
      requestPython,
      "propose_project_skill",
      "提出等待作者确认的项目编辑技能；不能保存为启用技能，也不能自行启用。",
      proposeProjectSkillParameters,
    ),
    createRpcTool(requestPython, "audit_chapter", "只读审计当前项目中已生成的一章。", chapterParameters),
    createRpcTool(
      requestPython,
      "read_authoring_context",
      "读取作者素材及章节计划状态。",
      Type.Object({
        chapter: Type.Optional(Type.Integer({ minimum: 1, maximum: 100000 })),
      }, strict),
    ),
    createRpcTool(
      requestPython,
      "capture_author_material",
      "把当前作者消息中的创作想法保存为待整理素材。",
      Type.Object({
        summary: shortText,
        category: Type.Optional(Type.String({ minLength: 1, maxLength: 100 })),
      }, strict),
    ),
    createRpcTool(
      requestPython,
      "save_author_plan",
      "保存等待作者下一轮确认的章节计划；不能代替作者批准。",
      savePlanParameters,
    ),
    createRpcTool(
      requestPython,
      "approve_author_plan",
      "依据当前作者消息批准既有最新计划；只批准，不执行。",
      planActionParameters,
    ),
    createRpcTool(
      requestPython,
      "execute_author_plan",
      "依据批准之后的新一轮作者指令，将计划交给写作管线。",
      planActionParameters,
    ),
    createRpcTool(
      requestPython,
      "update_work_plan",
      "更新当前工作计划面板，向作者展示工作步骤与进度。",
      workPlanParameters,
    ),
  ];
}
