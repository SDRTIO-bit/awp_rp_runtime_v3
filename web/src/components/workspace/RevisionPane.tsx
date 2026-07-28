import type { AcceptedChapter } from "../../api/workspace";

export function RevisionPane({ chapter }: { chapter: AcceptedChapter }) {
  return <section className="revision-pane" aria-label="正文修订定位">
    <header><strong>既有正文修订</strong><small>基于正文 r{chapter.accepted_revision} · {chapter.draft_id}</small></header>
    <p>正文保持只读。请在对话中引用段落编号，让编辑提出“原文 / 替换文 / 理由 / 影响”，并在后续两轮分别确认与应用。</p>
    {chapter.paragraphs.map((paragraph) => <article key={paragraph.paragraph_id}>
      <code>{paragraph.paragraph_id}</code><p>{paragraph.text}</p>
    </article>)}
  </section>;
}
