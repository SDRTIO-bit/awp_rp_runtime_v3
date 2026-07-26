import { useState } from "react";
import type { ToolActivityEntry } from "../../state/editorEvents";


export function ToolActivity({
  activity,
  approvals,
  onDecision,
}: {
  activity: Record<string, ToolActivityEntry>;
  approvals: Record<string, ToolActivityEntry>;
  onDecision: (approvalId: string, decision: "allow" | "deny", remember: boolean) => void;
}) {
  const [sending, setSending] = useState<Record<string, boolean>>({});
  const pending = Object.values(approvals);
  const recent = Object.values(activity).slice(-5).reverse();
  if (!pending.length && !recent.length) return null;

  const decide = (approvalId: string, decision: "allow" | "deny", remember: boolean) => {
    setSending((current) => ({ ...current, [approvalId]: true }));
    onDecision(approvalId, decision, remember);
  };

  return <section className="tool-workbench" aria-label="编辑工具活动">
    {pending.map((item) => <article className="tool-approval-card" key={item.approval_id}>
      <div className="tool-approval-title">
        <strong>需要你的审批</strong><span>{item.tool}</span>
      </div>
      <p>{item.summary}</p>
      {!!item.targets?.length && <code>{item.targets.join("、")}</code>}
      {item.reason && <small>{item.reason}</small>}
      <div className="tool-approval-actions">
        <button className="quiet-button" disabled={sending[item.approval_id]}
          onClick={() => decide(item.approval_id, "deny", false)}>拒绝</button>
        <button className="quiet-button" disabled={sending[item.approval_id]}
          onClick={() => decide(item.approval_id, "allow", true)}>本会话允许同类操作</button>
        <button className="primary-button" disabled={sending[item.approval_id]}
          onClick={() => decide(item.approval_id, "allow", false)}>本次允许</button>
      </div>
    </article>)}
    {!pending.length && <div className="tool-activity-strip">
      {recent.map((item) => <span key={item.approval_id} className={`tool-state ${item.status}`}>
        <b>{item.tool}</b>{item.summary}
      </span>)}
    </div>}
  </section>;
}
