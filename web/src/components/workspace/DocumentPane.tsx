import { useEffect, useMemo, useState, type ReactNode } from "react";
import { getChapterPlan, getDocument } from "../../api/workspace";
import { VersionedEditor } from "./VersionedEditor";

type Tab = "plan" | "draft" | "notes";
export function DocumentPane({
  projectId, room, writerBuffer = "",
  open = false,
  onClose,
  extraTabs,
}: { projectId: string; room: string; writerBuffer?: string; open?: boolean; onClose?: () => void; extraTabs?: ReactNode }) {
  const [tab, setTab] = useState<Tab>("plan");
  const [content, setContent] = useState("");
  const [error, setError] = useState("");
  const chapter = useMemo(() => room.startsWith("chapter:") ? Number(room.slice(8)) : 0, [room]);
  useEffect(() => {
    setError(""); setContent("");
    if (tab === "notes") { setContent("批注会在质量检查和编辑讨论后汇集到这里。"); return; }
    const task = tab === "plan"
      ? (chapter ? getChapterPlan(projectId, chapter).then((v) => JSON.stringify(v, null, 2)) : getDocument(projectId, "outline").then((v) => v.content))
      : (chapter ? getDocument(projectId, "draft", String(chapter)).then((v) => v.content) : Promise.resolve("请选择章节查看正文。"));
    task.then(setContent).catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [projectId, chapter, tab]);
  const shown = tab === "draft" && writerBuffer ? writerBuffer : content;
  return (
    <aside className={`document-pane ${open ? "mobile-open" : ""}`} aria-label="创作文档">
      <button className="mobile-drawer-close document-close" onClick={onClose} aria-label="关闭创作文档">×</button>
      <div className="document-tabs" role="tablist">
        <button role="tab" aria-selected={tab === "plan"} onClick={() => setTab("plan")}>计划</button>
        <button role="tab" aria-selected={tab === "draft"} onClick={() => setTab("draft")}>正文</button>
        <button role="tab" aria-selected={tab === "notes"} onClick={() => setTab("notes")}>批注</button>
      </div>
      <div className="document-meta"><span>只读预览</span><span>{chapter ? `第 ${chapter} 章` : "全书"}</span></div>
      <div className={`manuscript ${tab === "draft" ? "prose" : ""}`} role="tabpanel" aria-label={tab === "draft" ? "正文" : tab === "plan" ? "计划" : "批注"}>
        {error ? <div className="document-error">{error}</div> :
          tab === "draft" && chapter && !writerBuffer ? <VersionedEditor projectId={projectId} kind="draft" resourceId={String(chapter)} prose /> :
          tab === "plan" && !chapter ? <VersionedEditor projectId={projectId} kind="outline" /> :
          <pre>{shown || "正在载入…"}</pre>}
      </div>
    </aside>
  );
}
