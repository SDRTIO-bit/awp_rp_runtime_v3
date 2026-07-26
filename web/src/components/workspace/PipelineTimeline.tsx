const labels: Record<string, string> = {
  author_plan_compile: "编译作者计划", architect: "Architect", director: "Director",
  autonomous_npc_planning: "自主 NPC 规划", writer: "Writer 正文", quality: "质量检查",
  continuity: "连续性检查", polish: "精修", ledger: "账本", draft_saved: "正文版本已保存",
};
export function PipelineTimeline({ steps }: { steps: Array<{ phase: string; state: string }> }) {
  if (!steps.length) return null;
  return <section className="pipeline-timeline" aria-label="写作管线">
    <div className="pipeline-title">项目管线</div>
    {steps.map((step) => <div key={step.phase} className={`pipeline-step ${step.state}`}>
      <span className="pipeline-node" /><span>{labels[step.phase] ?? step.phase}</span><em>{step.state === "skipped" ? "作者主导，已跳过" : step.state === "running" ? "运行中" : "完成"}</em>
    </div>)}
  </section>;
}
