export function AuthorPlanCard({ plan, onApprove, onExecute }: {
  plan: Record<string, any>; onApprove: () => void; onExecute: () => void;
}) {
  const approved = plan.status === "approved" || plan.status === "executed";
  return <article className="plan-card">
    <div className="plan-card-head"><span>作者计划 · v{plan.revision}</span><strong>{plan.status === "executed" ? "已执行" : approved ? "已批准" : "等待确认"}</strong></div>
    <h3>{plan.title || `第 ${plan.chapter_index} 章计划`}</h3>
    {plan.purpose && <p>{plan.purpose}</p>}
    <div className="plan-actions">
      <button className="quiet-button" disabled={approved || Boolean(plan.unresolved_questions?.length)} onClick={onApprove}>确认计划</button>
      <button className="primary-button" disabled={!approved || plan.status === "executed"} onClick={onExecute}>交给管线写作</button>
    </div>
  </article>;
}
