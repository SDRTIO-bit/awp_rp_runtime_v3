import { useEffect, useState } from "react";
import { ApiConflictError, DocumentVersion, getDocument, listDocumentVersions, saveDocument } from "../../api/workspace";
import { VersionHistory } from "./VersionHistory";

export function VersionedEditor({ projectId, kind, resourceId = "", prose = false }: {
  projectId: string; kind: string; resourceId?: string; prose?: boolean;
}) {
  const [resource, setResource] = useState<DocumentVersion | null>(null);
  const [buffer, setBuffer] = useState(""); const [editing, setEditing] = useState(false);
  const [versions, setVersions] = useState<DocumentVersion[]>([]); const [error, setError] = useState("");
  const load = () => getDocument(projectId, kind, resourceId).then((value) => { setResource(value); setBuffer(value.content); });
  useEffect(() => { setError(""); setEditing(false); load().catch((e) => setError(String(e))); }, [projectId, kind, resourceId]);
  useEffect(() => {
    const guard = (event: BeforeUnloadEvent) => { if (editing && buffer !== resource?.content) event.preventDefault(); };
    window.addEventListener("beforeunload", guard); return () => window.removeEventListener("beforeunload", guard);
  }, [editing, buffer, resource]);
  const save = async () => {
    if (!resource) return;
    try {
      const saved = await saveDocument(projectId, kind, buffer, resource.revision, resourceId);
      setResource(saved); setEditing(false); setError("");
    } catch (e) {
      setError(e instanceof ApiConflictError ? `服务器已有更新（v${e.currentRevision}），你的编辑内容仍保留在这里。` : String(e));
    }
  };
  const history = async () => setVersions(await listDocumentVersions(projectId, kind, resourceId));
  if (error && !resource) return <div className="document-error">{error}</div>;
  return <div className={`versioned-editor ${prose ? "prose" : ""}`}>
    <div className="editor-actions">
      <span>{resource ? `v${resource.revision} · ${resource.source}` : "载入中"}</span>
      <button className="quiet-button" onClick={history}>历史</button>
      {!editing ? <button className="quiet-button" onClick={() => setEditing(true)}>编辑</button> : <>
        <button className="quiet-button" onClick={() => { setBuffer(resource?.content ?? ""); setEditing(false); }}>取消</button>
        <button className="primary-button" onClick={save}>保存新版本</button>
      </>}
    </div>
    {error && <div className="document-error">{error}</div>}
    {editing ? <textarea value={buffer} onChange={(e) => setBuffer(e.target.value)} /> : <pre>{resource?.content || "暂无内容"}</pre>}
    {versions.length > 0 && <VersionHistory versions={versions} onSelect={(v) => { setBuffer(v.content); setEditing(true); }} />}
  </div>;
}
