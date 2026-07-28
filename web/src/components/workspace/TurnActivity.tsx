import { useState } from "react";
import type { EditorTurn, ToolActivityEntry, ProjectMutationReceipt } from "../../state/editorEvents";

interface Props {
  turn: EditorTurn;
}

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    queued: "排队中", running: "执行中", waiting_approval: "等待审批",
    running_pipeline: "管线执行中", completed: "已完成", failed: "失败",
    cancelled: "已取消", interrupted: "已中断",
  };
  return map[status] ?? status;
}

export function TurnActivity({ turn }: Props) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const toggle = (key: string) => {
    setExpanded((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  if (!turn.activity.length && !turn.changes.length && !turn.error) return null;

  return (
    <div className="turn-activity" data-turn-id={turn.id}>
      <div className="turn-status-badge">{statusLabel(turn.status)}</div>

      {turn.error && <div className="turn-error">{turn.error}</div>}

      {turn.activity.length > 0 && (
        <div className="activity-section">
          {turn.activity.map((entry, i) => {
            const key = entry.approval_id || `act-${i}`;
            const isOpen = expanded[key] === true;
            return (
              <div key={key} className={`activity-card ${entry.status}`}>
                <button
                  className="activity-summary"
                  onClick={() => toggle(key)}
                  aria-expanded={isOpen}
                >
                  <span className={`status-dot ${entry.status}`} />
                  <span>{entry.tool}</span>
                  <span>{entry.summary}</span>
                </button>
                {isOpen && (
                  <div className="activity-detail">
                    {entry.targets && entry.targets.length > 0 && (
                      <div className="activity-targets">
                        目标: {entry.targets.join(", ")}
                      </div>
                    )}
                    {entry.reason && <div className="activity-reason">{entry.reason}</div>}
                    {entry.diff && (
                      <pre className="activity-diff">{entry.diff}</pre>
                    )}
                    {entry.decision && (
                      <div className={`activity-decision ${entry.decision}`}>
                        决定: {entry.decision === "allow" ? "允许" : "拒绝"}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {turn.changes.length > 0 && (
        <div className="changes-section">
          {turn.changes.map((change) => (
            <div key={change.change_id} className="change-card">
              <span className="change-op">{change.operation}</span>
              <span className="change-path">{change.path}</span>
              {change.diff && <pre className="change-diff">{change.diff.substring(0, 2000)}</pre>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
