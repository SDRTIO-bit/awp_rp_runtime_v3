import { useEffect, useState } from "react";
import { ChapterSummary, listChapters } from "../../api/workspace";

export function ProjectTree({
  projectId, room, onRoom, onPrompt, open = false, onClose,
}: {
  projectId: string; room: string; onRoom: (room: string) => void; onPrompt: () => void; open?: boolean; onClose?: () => void;
}) {
  const [chapters, setChapters] = useState<ChapterSummary[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    listChapters(projectId).then(setChapters).catch((e) => setError(String(e)));
  }, [projectId]);
  return (
    <aside className={`project-tree ${open ? "mobile-open" : ""}`} aria-label="项目目录">
      <button className="mobile-drawer-close" onClick={onClose} aria-label="关闭项目目录">×</button>
      <div className="tree-project">
        <span className="tree-kicker">本地小说项目</span>
        <strong>{projectId}</strong>
      </div>
      <nav>
        <button className={room === "book" ? "selected" : ""} onClick={() => onRoom("book")}>
          <span>⌂</span><span>全书编辑室<small>总纲、世界、人物</small></span>
        </button>
        <div className="tree-section">章节房间</div>
        {chapters.map((chapter) => {
          const key = `chapter:${chapter.chapter_index}`;
          return <button key={key} className={room === key ? "selected" : ""} onClick={() => onRoom(key)}>
            <span>{String(chapter.chapter_index).padStart(2, "0")}</span>
            <span>{chapter.title || `第${chapter.chapter_index}章`}<small>独立编辑会话</small></span>
          </button>;
        })}
        {!chapters.length && !error && <p className="tree-empty">尚无章节计划</p>}
        {error && <p className="tree-error">章节载入失败</p>}
        <div className="tree-section">工具</div>
        <button onClick={onPrompt}><span>⚙</span><span>AI 模型设置<small>供应商、模型与角色提示词</small></span></button>
      </nav>
      <div className="tree-foot"><span className="status-dot" /> 本地运行 · 已连接项目</div>
    </aside>
  );
}
