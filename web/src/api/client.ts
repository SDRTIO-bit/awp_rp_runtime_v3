const BASE = "";

interface ApiEnvelope<T> {
  data?: T;
}

function errorMessage(body: ApiEnvelope<unknown> | undefined, status: number): string {
  const data = body?.data;
  if (
    typeof data === "object" &&
    data !== null &&
    "error" in data &&
    typeof data.error === "string"
  ) {
    return data.error;
  }
  return `Request failed (${status})`;
}

async function parseJson<T>(res: Response): Promise<ApiEnvelope<T>> {
  return (await res.json()) as ApiEnvelope<T>;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}/awp/api/v1${path}`);
  const body = await parseJson<T>(res);
  if (!res.ok) throw new Error(errorMessage(body, res.status));
  return body.data as T;
}

async function post<T>(path: string, payload?: unknown): Promise<T> {
  const res = await fetch(`${BASE}/awp/api/v1${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload ?? {}),
  });
  const body = await parseJson<T>(res);
  if (!res.ok) throw new Error(errorMessage(body, res.status));
  return body.data as T;
}

async function del<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}/awp/api/v1${path}`, { method: "DELETE" });
  const body = await parseJson<T>(res);
  if (!res.ok) throw new Error(errorMessage(body, res.status));
  return body.data as T;
}

export interface NovelProject {
  project_id: string;
  title: string;
  genre: string;
  target_platform: string;
  target_reader: string;
  core_emotion: string;
  one_sentence_pitch: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface NovelCharacter {
  character_id: string;
  project_id: string;
  name: string;
  role: string;
  personality: string;
  core_motivation: string;
  current_state: Record<string, unknown>;
}

export interface NovelChapterPlan {
  chapter_id: string;
  chapter_index: number;
  title: string;
  target_chars: number;
  target_emotion: string;
  scene_beats: Array<{
    beat_id: string;
    description: string;
    function_tag: string;
    density: string;
    budget_chars: number;
  }>;
  ending_design: {
    hook_type: string;
    hook_detail: string;
    hook_strength: string;
  };
}

export interface NovelDraft {
  draft_id: string;
  chapter_id: string;
  revision: number;
  text: string;
  char_count: number;
  status: string;
}

export interface NovelLedgerItem {
  item_id: string;
  section: string;
  entity: string;
  content: string;
  status: string;
  source_chapter: number;
}

export interface NovelPlanResult {
  title: string;
  genre: string;
  one_sentence_pitch: string;
  core_outline: { surface: string; inner: string; one_sentence: string };
  world_setting: Record<string, unknown>;
  characters: Array<{
    name: string;
    role: string;
    core_trait: string;
    motivation: string;
  }>;
  volumes: Array<{
    volume_index: number;
    title: string;
    objective: string;
    key_results: string[];
  }>;
  first_volume_chapters: Array<{
    chapter_index: number;
    objective: string;
    key_results: string[];
    hook_type: string;
  }>;
  tags: string[];
}

export interface AutonomySummary {
  project_id: string;
  active_count: number;
  stale_count: number;
  chapter_action_counts: Record<string, number>;
}

export async function listNovelProjects(): Promise<NovelProject[]> {
  return get<NovelProject[]>("/novels");
}

export async function getNovelProject(projectId: string): Promise<NovelProject> {
  return get<NovelProject>(`/novels/${encodeURIComponent(projectId)}`);
}

export async function deleteNovelProject(projectId: string): Promise<void> {
  await del<{ success: boolean }>(`/novels/${encodeURIComponent(projectId)}`);
}

export async function planNovelFromConcept(params: {
  concept: string;
  title?: string;
  genre?: string;
  target_platform?: string;
  additional_requirements?: string;
}): Promise<NovelPlanResult> {
  return post<NovelPlanResult>("/novels/plan", params);
}

export async function listNovelCharacters(
  projectId: string,
): Promise<NovelCharacter[]> {
  return get<NovelCharacter[]>(
    `/novels/${encodeURIComponent(projectId)}/characters`,
  );
}

export async function listNovelChapterPlans(
  projectId: string,
): Promise<NovelChapterPlan[]> {
  return get<NovelChapterPlan[]>(
    `/novels/${encodeURIComponent(projectId)}/chapters`,
  );
}

export async function writeNovelChapter(
  projectId: string,
  chapterIndex: number,
): Promise<NovelDraft> {
  return post<NovelDraft>(
    `/novels/${encodeURIComponent(projectId)}/chapters/${chapterIndex}/write`,
  );
}

export interface LlmRoleOverride {
  model?: string;
  max_tokens?: number;
  thinking_level?: string;
  provider?: string;
  api_base?: string;
  api_key_env?: string;
}

export interface LlmConfig {
  overrides: Record<string, LlmRoleOverride>;
  defaults: Record<string, LlmRoleOverride>;
}

export async function getLlmConfig(projectId: string): Promise<LlmConfig> {
  return get<LlmConfig>(`/novels/${encodeURIComponent(projectId)}/llm-config`);
}

export async function updateLlmConfig(
  projectId: string,
  overrides: Record<string, Partial<LlmRoleOverride>>,
): Promise<{ ok: boolean; overrides: Record<string, LlmRoleOverride> }> {
  return post(`/novels/${encodeURIComponent(projectId)}/llm-config`, { overrides });
}
