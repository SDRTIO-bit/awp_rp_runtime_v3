export interface EditorEvent {
  event_id?: number;
  project_id?: string;
  room?: string;
  type: string;
  payload: Record<string, any>;
}
export interface EditorMessage { id: string; role: "author" | "editor"; text: string; source?: string; }
export interface PipelineStep { phase: string; state: string; data?: Record<string, any>; }
export interface EditorEventState {
  lastEventId: number; seen: Set<number>; messages: EditorMessage[];
  partial: Record<string, string>; plans: Record<string, Record<string, any>>;
  pipeline: PipelineStep[]; writerBuffer: string; errors: string[];
}
export const emptyEditorState = (): EditorEventState => ({
  lastEventId: 0, seen: new Set(), messages: [], partial: {}, plans: {},
  pipeline: [], writerBuffer: "", errors: [],
});

export function applyEditorEvent(state: EditorEventState, event: EditorEvent): EditorEventState {
  const id = event.event_id ?? 0;
  if (id && state.seen.has(id)) return state;
  const next: EditorEventState = {
    ...state, seen: new Set(state.seen), messages: [...state.messages],
    partial: { ...state.partial }, plans: { ...state.plans },
    pipeline: [...state.pipeline], errors: [...state.errors],
    lastEventId: Math.max(state.lastEventId, id),
  };
  if (id) next.seen.add(id);
  const p = event.payload ?? {};
  if (event.type === "author_message_saved") {
    next.messages.push({ id: p.client_message_id ?? `author-${id}`, role: "author", text: p.text ?? "", source: p.source });
  } else if (event.type === "editor_delta") {
    const messageId = p.message_id ?? "active";
    next.partial[messageId] = (next.partial[messageId] ?? "") + (p.text ?? "");
  } else if (event.type === "editor_message_completed") {
    const messageId = p.message_id ?? `editor-${id}`;
    next.messages.push({ id: messageId, role: "editor", text: p.text ?? next.partial[messageId] ?? "" });
    delete next.partial[messageId];
  } else if (event.type === "author_plan_saved" || event.type === "author_plan_approved" || event.type === "author_plan_executed") {
    next.plans[p.plan_id] = { ...(next.plans[p.plan_id] ?? {}), ...p };
  } else if (event.type === "pipeline_phase") {
    const step = { phase: p.phase, state: p.event === "start" ? "running" : p.event === "skipped" ? "skipped" : "completed", data: p.data };
    next.pipeline = [...next.pipeline.filter((item) => item.phase !== p.phase), step];
  } else if (event.type === "writer_delta") {
    next.writerBuffer += p.text ?? "";
  } else if (event.type === "draft_version_saved") {
    next.pipeline = [...next.pipeline, { phase: "draft_saved", state: "completed", data: p }];
  } else if (["turn_failed", "action_rejected", "protocol_error"].includes(event.type)) {
    next.errors.push(p.message ?? "操作失败");
  }
  return next;
}
