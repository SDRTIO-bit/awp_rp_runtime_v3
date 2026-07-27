import { useCallback } from "react";
import type { EditorTurn } from "../../state/editorEvents";

interface Props {
  turns: Record<string, EditorTurn>;
  turnIds: string[];
}

export function ChangesPane({ turns, turnIds }: Props) {
  const allChanges = turnIds.flatMap((id) => {
    const turn = turns[id];
    if (!turn) return [];
    return turn.changes.map((c) => ({ ...c, turnId: id }));
  });

  if (!allChanges.length) {
    return (
      <div className="changes-pane empty">
        <p>本分支暂无项目文件改动。</p>
      </div>
    );
  }

  return (
    <div className="changes-pane">
      <h3>文件改动历史</h3>
      {allChanges.map((change, i) => (
        <div key={change.change_id ?? i} className="change-entry">
          <div className="change-meta">
            <span className={`change-op-badge ${change.operation}`}>
              {change.operation === "restore" ? "恢复" : change.operation === "write" ? "写入" : "编辑"}
            </span>
            <span className="change-path">{change.path}</span>
          </div>
          {change.diff && (
            <details>
              <summary>查看差异</summary>
              <pre className="change-diff">{change.diff.substring(0, 4000)}</pre>
            </details>
          )}
        </div>
      ))}
    </div>
  );
}
