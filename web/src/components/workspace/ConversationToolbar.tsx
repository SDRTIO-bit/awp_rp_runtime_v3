import { useState, useEffect, useCallback } from "react";
import {
  ConversationBranch,
  listConversations,
  createConversation,
  updateConversation,
  searchConversations,
} from "../../api/workspace";

interface Props {
  projectId: string;
  room: string;
  selectedBranchId: string;
  onSelect: (branchId: string) => void;
  onNew?: () => void;
  onFork?: (parentId: string, forkEventId: number, title: string) => Promise<void>;
  busy?: boolean;
}

export function ConversationToolbar({
  projectId, room, selectedBranchId, onSelect, onNew, onFork, busy,
}: Props) {
  const [branches, setBranches] = useState<ConversationBranch[]>([]);
  const [showArchived, setShowArchived] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [renaming, setRenaming] = useState<string | null>(null);
  const [renameTitle, setRenameTitle] = useState("");

  const load = useCallback(async () => {
    try {
      const list = await listConversations(projectId, room, showArchived);
      setBranches(list);
    } catch { /* ignore */ }
  }, [projectId, room, showArchived]);

  useEffect(() => { load(); }, [load]);

  const handleNew = async () => {
    if (busy) return;
    if (onNew) { onNew(); return; }
    const title = prompt("新对话标题（1-80 字符）：");
    if (!title || title.length > 80) return;
    try {
      const branch = await createConversation(projectId, room, { title });
      onSelect(branch.branch_id);
      load();
    } catch { /* ignore */ }
  };

  const handleRename = async (branchId: string) => {
    if (!renameTitle.trim() || renameTitle.length > 80) return;
    try {
      await updateConversation(projectId, room, branchId, { title: renameTitle.trim() });
      setRenaming(null);
      setRenameTitle("");
      load();
    } catch { /* ignore */ }
  };

  const handleArchive = async (branchId: string) => {
    try {
      await updateConversation(projectId, room, branchId, { archived: true });
      if (branchId === selectedBranchId) {
        const active = branches.find((b) => b.branch_id !== branchId && b.status === "active");
        if (active) onSelect(active.branch_id);
        else if (onNew) onNew();
      }
      load();
    } catch { /* ignore */ }
  };

  const selected = branches.find((b) => b.branch_id === selectedBranchId);

  return (
    <div className="conversation-toolbar" role="toolbar" aria-label="对话版本管理">
      <select
        className="branch-select"
        value={selectedBranchId}
        onChange={(e) => onSelect(e.target.value)}
        disabled={busy}
        aria-label="选择对话版本"
      >
        {branches.map((b) => (
          <option key={b.branch_id} value={b.branch_id}>
            {b.title || b.branch_id}
          </option>
        ))}
      </select>

      <button className="toolbar-btn" onClick={handleNew} disabled={busy} aria-label="新建对话">
        新建
      </button>

      {selected && selected.branch_id !== "main" && (
        <>
          {renaming === selected.branch_id ? (
            <span className="rename-inline">
              <input
                value={renameTitle}
                onChange={(e) => setRenameTitle(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleRename(selected.branch_id)}
                maxLength={80}
                aria-label="重命名版本"
              />
              <button onClick={() => handleRename(selected.branch_id)} aria-label="确认重命名">✓</button>
              <button onClick={() => { setRenaming(null); setRenameTitle(""); }} aria-label="取消重命名">✗</button>
            </span>
          ) : (
            <>
              <button className="toolbar-btn" onClick={() => { setRenaming(selected.branch_id); setRenameTitle(selected.title); }} disabled={busy} aria-label="重命名版本">
                重命名
              </button>
              <button className="toolbar-btn" onClick={() => handleArchive(selected.branch_id)} disabled={busy} aria-label="归档版本">
                归档
              </button>
            </>
          )}
        </>
      )}

      <label className="archived-toggle">
        <input type="checkbox" checked={showArchived} onChange={() => setShowArchived(!showArchived)} />
        显示已归档
      </label>
    </div>
  );
}
