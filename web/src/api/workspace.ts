const root = "/awp/api/v1/novels";

export interface DocumentVersion {
  document_id: string;
  kind: "outline" | "world" | "characters" | "draft";
  resource_id: string;
  revision: number;
  content: string;
  content_hash: string;
  source: string;
  created_at: string;
}
export interface PromptResource {
  role: string; content: string; source: "system" | "project";
  revision: number; content_hash: string; created_at?: string;
}
export interface ChapterSummary {
  chapter_id: string; chapter_index: number; title: string;
  target_chars: number; [key: string]: unknown;
}

export class ApiConflictError extends Error {
  currentRevision: number;
  constructor(message: string, currentRevision: number) {
    super(message); this.currentRevision = currentRevision;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  const body = await response.json();
  if (!response.ok) {
    const message = body?.data?.error ?? `请求失败 (${response.status})`;
    if (response.status === 409) throw new ApiConflictError(message, body.data.current_revision);
    throw new Error(message);
  }
  return body.data as T;
}

const query = (resourceId?: string) =>
  resourceId ? `?resource_id=${encodeURIComponent(resourceId)}` : "";

export const getDocument = (projectId: string, kind: string, resourceId = "") =>
  request<DocumentVersion>(`${root}/${encodeURIComponent(projectId)}/documents/${kind}${query(resourceId)}`);
export const listDocumentVersions = (projectId: string, kind: string, resourceId = "") =>
  request<DocumentVersion[]>(`${root}/${encodeURIComponent(projectId)}/documents/${kind}/versions${query(resourceId)}`);
export const saveDocument = (projectId: string, kind: string, content: string, expectedRevision: number, resourceId = "") =>
  request<DocumentVersion>(`${root}/${encodeURIComponent(projectId)}/documents/${kind}${query(resourceId)}`, {
    method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content, expected_revision: expectedRevision }),
  });
export const listChapters = (projectId: string) =>
  request<ChapterSummary[]>(`${root}/${encodeURIComponent(projectId)}/chapters`);
export const getChapterPlan = (projectId: string, index: number) =>
  request<Record<string, unknown>>(`${root}/${encodeURIComponent(projectId)}/chapters/${index}/plan`);
export const listPrompts = (projectId: string) =>
  request<PromptResource[]>(`${root}/${encodeURIComponent(projectId)}/prompts`);
export const getPrompt = (projectId: string, role: string) =>
  request<PromptResource>(`${root}/${encodeURIComponent(projectId)}/prompts/${role}`);
export const savePrompt = (projectId: string, role: string, content: string, expectedRevision: number) =>
  request<PromptResource>(`${root}/${encodeURIComponent(projectId)}/prompts/${role}`, {
    method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content, expected_revision: expectedRevision }),
  });
export const promptDiff = (projectId: string, role: string) =>
  request<{ diff: string }>(`${root}/${encodeURIComponent(projectId)}/prompts/${role}/diff`);
