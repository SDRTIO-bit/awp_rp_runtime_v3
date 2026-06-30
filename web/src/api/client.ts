const BASE = "";

interface ApiEnvelope<T> {
  data?: T;
}

export interface Session {
  session_id: string;
  card_id: string;
  card_name: string;
  greeting_id: string;
  turn_count: number;
  last_turn_time: string;
  created_at: string;
  status: string;
}

export interface Turn {
  turn_id: string;
  turn_index: number;
  mode: string;
  player_input: string;
  writer_output: string;
  base_card_state_revision: number;
  result_card_state_revision: number;
  accepted_at: string;
  created_at: string;
}

export interface Card {
  card_id: string;
  version: number;
  name: string;
  status: string;
  greeting_count: number;
  worldbook_count: number;
  created_at: string;
}

export interface Opening {
  opening_record_id: string;
  greeting_id: string;
  content: string;
  created_at: string;
}

export type ExecutionMode = "hybrid" | "python" | "";

export interface ExecutionOptions {
  mode?: string;
  workflow?: string;
}

export interface TurnCommandResult {
  success: boolean;
  turn_id?: string;
  turn_index?: number;
  quality?: string;
  writer_output?: string;
}

export interface StepPayload {
  [key: string]: unknown;
}

export type StreamEvent =
  | { type: "started"; turn_id: string; steps: string[] }
  | { type: "step"; step: string; payload: StepPayload; duration_ms: number }
  | { type: "writer_text"; turn_id: string; writer_output: string }
  | {
      type: "done";
      success: boolean;
      turn_id?: string;
      turn_index?: number;
      writer_output?: string;
      error?: string;
      failure_code?: string;
    };

export interface ImportCardResult {
  success: boolean;
  session_id: string;
  card_id: string;
  diagnostics?: Record<string, unknown>;
}

export interface GreetingInfo {
  greeting_id: string;
  label: string;
  is_default: boolean;
  preview: string;
}

export interface CreateSessionResult {
  session_id: string;
  card_id: string;
  greeting_id: string;
  diagnostics?: Record<string, unknown>;
}

export interface WorkflowInfo {
  name: string;
  node_count: number;
  class_types: string[];
}

export interface WriterPresetInfo {
  name: string;
  content: string;
  path: string;
}

function errorMessage(body: ApiEnvelope<{ error?: string }> | undefined, status: number): string {
  return body?.data?.error || `HTTP ${status}`;
}

async function parseJson<T>(res: Response): Promise<ApiEnvelope<T>> {
  return (await res.json()) as ApiEnvelope<T>;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}/awp/api/v1${path}`);
  const body = await parseJson<T>(res);
  if (!res.ok) throw new Error(errorMessage(body as ApiEnvelope<{ error?: string }>, res.status));
  return body.data as T;
}

async function post<T>(path: string, payload?: unknown): Promise<T> {
  const res = await fetch(`${BASE}/awp/api/v1${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: payload === undefined ? undefined : JSON.stringify(payload),
  });
  const body = await parseJson<T>(res);
  if (!res.ok) throw new Error(errorMessage(body as ApiEnvelope<{ error?: string }>, res.status));
  return body.data as T;
}

async function del<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}/awp/api/v1${path}`, { method: "DELETE" });
  const body = await parseJson<T>(res);
  if (!res.ok) throw new Error(errorMessage(body as ApiEnvelope<{ error?: string }>, res.status));
  return body.data as T;
}

function withExecutionQuery(path: string, opts?: ExecutionOptions): string {
  const params = new URLSearchParams();
  if (opts?.mode) params.set("mode", opts.mode);
  if (opts?.workflow) params.set("workflow", opts.workflow);
  const query = params.toString();
  return query ? `${path}?${query}` : path;
}

export async function listSessions(): Promise<Session[]> {
  return get<Session[]>("/sessions");
}

export async function getSession(id: string): Promise<Session & { opening_content: string }> {
  return get(`/sessions/${encodeURIComponent(id)}`);
}

export async function listTurns(sessionId: string): Promise<Turn[]> {
  return get<Turn[]>(`/sessions/${encodeURIComponent(sessionId)}/turns`);
}

export async function getOpening(sessionId: string): Promise<Opening> {
  return get<Opening>(`/sessions/${encodeURIComponent(sessionId)}/opening`);
}

export async function listCards(): Promise<Card[]> {
  return get<Card[]>("/cards");
}

export async function continueSession(sessionId: string): Promise<{ success: boolean; turn_id: string; turn_index: number; quality: string; writer_output: string }> {
  return continueSessionV2(sessionId) as Promise<{ success: boolean; turn_id: string; turn_index: number; quality: string; writer_output: string }>;
}

export async function sendTurn(
  sessionId: string,
  playerInput: string,
  opts?: ExecutionOptions,
): Promise<TurnCommandResult> {
  return post<TurnCommandResult>(
    withExecutionQuery(`/sessions/${encodeURIComponent(sessionId)}/turn`, opts),
    { player_input: playerInput },
  );
}

export function parseSSEBlock(block: string): StreamEvent | null {
  let type = "";
  const dataLines: string[] = [];
  for (const rawLine of block.split(/\r?\n/)) {
    const line = rawLine.trimEnd();
    if (line.startsWith("event:")) {
      type = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trimStart());
    }
  }
  if (!type || dataLines.length === 0) return null;
  const data = JSON.parse(dataLines.join("\n")) as Record<string, unknown>;
  return { type, ...data } as StreamEvent;
}

export async function sendTurnStream(
  sessionId: string,
  playerInput: string,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(
    `${BASE}/awp/api/v1/sessions/${encodeURIComponent(sessionId)}/turn/stream`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ player_input: playerInput }),
      signal,
    },
  );
  if (!res.ok) {
    let message = `HTTP ${res.status}`;
    try {
      message = errorMessage(await parseJson<{ error?: string }>(res), res.status);
    } catch {
      // Keep the HTTP status if the server did not return JSON.
    }
    throw new Error(message);
  }
  if (!res.body) throw new Error("流式响应正文不可用");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split(/\r?\n\r?\n/);
    buffer = parts.pop() || "";
    for (const part of parts) {
      const event = parseSSEBlock(part);
      if (event) onEvent(event);
    }
  }
  buffer += decoder.decode();
  const trailing = buffer.trim();
  if (trailing) {
    const event = parseSSEBlock(trailing);
    if (event) onEvent(event);
  }
}

export async function firstTurn(
  sessionId: string,
  playerInput: string,
  opts?: ExecutionOptions,
): Promise<TurnCommandResult> {
  return post<TurnCommandResult>(
    withExecutionQuery(`/sessions/${encodeURIComponent(sessionId)}/first-turn`, opts),
    { player_input: playerInput },
  );
}

export async function continueSessionV2(
  sessionId: string,
  opts?: ExecutionOptions,
): Promise<TurnCommandResult> {
  return post<TurnCommandResult>(
    withExecutionQuery(`/sessions/${encodeURIComponent(sessionId)}/continue`, opts),
  );
}

export async function importCard(sourcePath: string, greetingId?: string): Promise<ImportCardResult> {
  return post<ImportCardResult>("/cards/import", {
    source_path: sourcePath,
    ...(greetingId ? { greeting_id: greetingId } : {}),
  });
}

export async function deleteCard(cardId: string): Promise<void> {
  await del<{ success: boolean }>(`/cards/${encodeURIComponent(cardId)}`);
}

export async function deleteSession(sessionId: string): Promise<void> {
  await del<{ success: boolean }>(`/sessions/${encodeURIComponent(sessionId)}`);
}

export async function listGreetings(cardId: string): Promise<GreetingInfo[]> {
  return get<GreetingInfo[]>(`/cards/${encodeURIComponent(cardId)}/greetings`);
}

export async function createSession(cardId: string, greetingId: string): Promise<CreateSessionResult> {
  return post<CreateSessionResult>("/sessions", {
    card_id: cardId,
    greeting_id: greetingId,
  });
}

export async function listWorkflows(): Promise<WorkflowInfo[]> {
  return get<WorkflowInfo[]>("/workflows");
}

export async function listWriterPresets(): Promise<string[]> {
  return get<string[]>("/presets/writer");
}

export async function getWriterPreset(name: string): Promise<WriterPresetInfo> {
  return get<WriterPresetInfo>(`/presets/writer/${encodeURIComponent(name)}`);
}
