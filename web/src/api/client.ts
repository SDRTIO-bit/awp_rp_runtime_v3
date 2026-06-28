const BASE = "";

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

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}/awp/api/v1${path}`);
  const body = await res.json();
  if (!res.ok) throw new Error(body.data?.error || `HTTP ${res.status}`);
  return body.data as T;
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
  const res = await fetch(`${BASE}/awp/api/v1/sessions/${encodeURIComponent(sessionId)}/continue`, { method: "POST" });
  const body = await res.json();
  if (!res.ok) throw new Error(body.data?.error || `HTTP ${res.status}`);
  return body.data;
}
