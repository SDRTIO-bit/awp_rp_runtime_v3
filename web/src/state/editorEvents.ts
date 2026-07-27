export interface EditorEvent {
  event_id?: number;
  project_id?: string;
  room?: string;
  branch_id?: string;
  turn_id?: string;
  type: string;
  payload: Record<string, any>;
}
export interface EditorMessage {
  id: string; role: "author" | "editor"; text: string; source?: string;
  eventId?: number; turnId?: string; incomplete?: boolean;
}
export interface EditorTurn {
  id: string; status: TurnStatus; messageIds: string[];
  activity: ToolActivityEntry[]; changes: ProjectMutationReceipt[];
  pipeline: PipelineStep[]; error?: string;
}
export type TurnStatus = "queued" | "running" | "waiting_approval" | "running_pipeline" | "completed" | "failed" | "cancelled" | "interrupted";
export interface PipelineStep { phase: string; state: string; data?: Record<string, any>; }
export interface ToolActivityEntry {
  approval_id: string; tool: string; status: string; summary: string;
  targets?: string[]; reason?: string; decision?: string; diff?: string;
}
export interface ProjectMutationReceipt {
  change_id: string; turn_id: string; branch_id: string;
  path: string; operation: string; before_hash: string;
  after_hash: string; diff: string; history_version_id: string;
}
export interface EditorEventState {
  lastEventId: number; seen: Set<string>; messages: EditorMessage[];
  turns: Record<string, EditorTurn>; turnIds: string[];
  partial: Record<string, string>; plans: Record<string, Record<string, any>>;
  pipeline: PipelineStep[]; writerBuffer: string; errors: string[];
  toolActivity: Record<string, ToolActivityEntry>;
  pendingApprovals: Record<string, ToolActivityEntry>;
}
export const emptyEditorState = (): EditorEventState => ({
  lastEventId: 0, seen: new Set(), messages: [], turns: {}, turnIds: [],
  partial: {}, plans: {},
  pipeline: [], writerBuffer: "", errors: [], toolActivity: {}, pendingApprovals: {},
});

function _seenKey(event: EditorEvent): string {
  return `${event.branch_id ?? "main"}:${event.event_id ?? 0}`;
}

export function applyEditorEvent(state: EditorEventState, event: EditorEvent): EditorEventState {
  const id = event.event_id ?? 0;
  const key = _seenKey(event);

  // Handle reset (branch switch)
  if (event.type === "__reset__") {
    return emptyEditorState();
  }

  if (id && state.seen.has(key)) return state;
  const turnId = event.turn_id;
  const next: EditorEventState = {
    ...state, seen: new Set(state.seen), messages: [...state.messages],
    partial: { ...state.partial }, plans: { ...state.plans },
    pipeline: [...state.pipeline], errors: [...state.errors],
    toolActivity: { ...state.toolActivity },
    pendingApprovals: { ...state.pendingApprovals },
    turns: { ...state.turns }, turnIds: [...state.turnIds],
    lastEventId: Math.max(state.lastEventId, id),
  };
  if (id) next.seen.add(key);

  // Turn state tracking
  const _ensureTurn = (status: string) => {
    if (turnId && !next.turns[turnId]) {
      next.turns[turnId] = { id: turnId, status: status as TurnStatus, messageIds: [], activity: [], changes: [], pipeline: [] };
      next.turnIds = [...next.turnIds, turnId];
    }
    if (turnId) {
      next.turns = { ...next.turns };
      next.turns[turnId] = { ...next.turns[turnId] };
    }
  };

  const p = event.payload ?? {};
  if (event.type === "turn_started") {
    _ensureTurn("running");
  } else if (event.type === "author_message_saved") {
    next.errors = [];
    const msg: EditorMessage = { id: p.client_message_id ?? `author-${id}`, role: "author", text: p.text ?? "", source: p.source, eventId: id, turnId };
    next.messages.push(msg);
    _ensureTurn("running");
    if (turnId) next.turns[turnId].messageIds.push(msg.id);
  } else if (event.type === "editor_delta") {
    const messageId = p.message_id ?? "active";
    next.partial[messageId] = (next.partial[messageId] ?? "") + (p.text ?? "");
  } else if (event.type === "editor_message_completed") {
    const messageId = p.message_id ?? `editor-${id}`;
    const msg: EditorMessage = { id: messageId, role: "editor", text: p.text ?? next.partial[messageId] ?? "", turnId, eventId: id };
    next.messages.push(msg);
    delete next.partial[messageId];
    if (turnId) next.turns[turnId].messageIds.push(msg.id);
  } else if (event.type === "turn_completed") {
    _ensureTurn("completed");
    if (turnId) next.turns[turnId].status = "completed";
  } else if (event.type === "turn_failed") {
    _ensureTurn("failed");
    if (turnId) { next.turns[turnId].status = "failed"; next.turns[turnId].error = p.message ?? "操作失败"; }
    for (const [msgId, text] of Object.entries(next.partial)) {
      if (text) next.messages.push({ id: msgId, role: "editor", text, incomplete: true, turnId });
    }
    next.partial = {};
    next.errors.push(p.message ?? "操作失败");
  } else if (event.type === "turn_interrupted") {
    _ensureTurn("interrupted");
    if (turnId) { next.turns[turnId].status = "interrupted"; next.turns[turnId].error = p.message ?? "服务重启"; }
    for (const [msgId, text] of Object.entries(next.partial)) {
      if (text) next.messages.push({ id: msgId, role: "editor", text, incomplete: true, turnId });
    }
    next.partial = {};
  } else if (event.type === "turn_cancelled") {
    _ensureTurn("cancelled");
    if (turnId) next.turns[turnId].status = "cancelled";
    next.partial = {};
  } else if (event.type === "project_file_changed") {
    _ensureTurn("running");
    if (turnId) next.turns[turnId].changes.push({
      change_id: p.change_id ?? `chg-${id}`, turn_id: turnId, branch_id: event.branch_id ?? "main",
      path: p.path ?? "", operation: p.operation ?? "write",
      before_hash: p.before_hash ?? "", after_hash: p.after_hash ?? "",
      diff: p.diff ?? "", history_version_id: p.history_version_id ?? "",
    });
  } else if (event.type === "tool_activity") {
    _ensureTurn("running");
    const approvalId = p.approval_id ?? `tool-${id}`;
    const entry: ToolActivityEntry = {
      ...(next.toolActivity[approvalId] ?? {}),
      approval_id: approvalId,
      tool: p.tool ?? "tool",
      status: p.status ?? "running",
      summary: p.summary ?? p.tool ?? "工具操作",
      targets: p.targets, reason: p.reason,
    };
    next.toolActivity[approvalId] = entry;
    if (turnId) next.turns[turnId].activity.push(entry);
  } else if (event.type === "tool_approval_requested") {
    _ensureTurn("waiting_approval");
    if (turnId) next.turns[turnId].status = "waiting_approval";
    const approvalId = p.approval_id;
    if (approvalId) {
      const approval: ToolActivityEntry = {
        approval_id: approvalId, tool: p.tool ?? "tool", status: "waiting",
        summary: p.summary ?? "等待审批", targets: p.targets, reason: p.reason, diff: p.diff,
      };
      next.pendingApprovals[approvalId] = approval;
      next.toolActivity[approvalId] = approval;
      if (turnId) next.turns[turnId].activity.push(approval);
    }
  } else if (event.type === "tool_approval_resolved") {
    const approvalId = p.approval_id;
    if (approvalId) {
      const prev = next.toolActivity[approvalId] ?? next.pendingApprovals[approvalId];
      if (prev) {
        const resolved: ToolActivityEntry = { ...prev, status: p.decision === "allow" ? "approved" : "denied", decision: p.decision };
        next.toolActivity[approvalId] = resolved;
        if (turnId) next.turns[turnId].activity.push(resolved);
      }
      delete next.pendingApprovals[approvalId];
    }
  } else if (event.type === "editor_work_plan_updated") {
    _ensureTurn("running");
  } else if (event.type === "worker_started" || event.type === "worker_completed" || event.type === "worker_failed") {
    _ensureTurn("running");
  } else if (event.type === "author_plan_saved" || event.type === "author_plan_approved" || event.type === "author_plan_executed") {
    next.plans[p.plan_id] = { ...(next.plans[p.plan_id] ?? {}), ...p };
  } else if (event.type === "pipeline_phase") {
    const step: PipelineStep = { phase: p.phase, state: p.event === "start" ? "running" : p.event === "skipped" ? "skipped" : "completed", data: p.data };
    next.pipeline = [...next.pipeline.filter((item) => item.phase !== p.phase), step];
    _ensureTurn("running_pipeline");
    if (turnId) { next.turns[turnId].status = "running_pipeline"; next.turns[turnId].pipeline.push(step); }
  } else if (event.type === "writer_delta") {
    next.writerBuffer += p.text ?? "";
  } else if (event.type === "draft_version_saved") {
    next.pipeline = [...next.pipeline, { phase: "draft_saved", state: "completed", data: p }];
  } else if (["action_rejected", "protocol_error"].includes(event.type)) {
    next.errors.push(p.message ?? "操作失败");
  }
  return next;
}
