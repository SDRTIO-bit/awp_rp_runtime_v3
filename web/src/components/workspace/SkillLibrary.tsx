import { useEffect, useState } from "react";
import {
  activateProjectSkill, deactivateProjectSkill, listProjectSkills,
  saveProjectSkill, type ProjectSkillLibrary,
} from "../../api/workspace";

const template = (id: string) => `---\nname: ${id}\ndescription: 描述这个编辑技能的检查范围\n---\n\n只报告可追溯的编辑证据。`;

export function SkillLibrary({ projectId }: { projectId: string }) {
  const [library, setLibrary] = useState<ProjectSkillLibrary>({ versions: [], enabled: [], proposals: [] });
  const [skillId, setSkillId] = useState("voice-check");
  const [content, setContent] = useState(template("voice-check"));
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const reload = () => listProjectSkills(projectId).then(setLibrary).catch((e) => setError(String(e)));
  useEffect(() => { void reload(); }, [projectId]);
  const enabled = new Set(library.enabled.map((item) => `${item.skill_id}:${item.version}`));
  const save = async () => {
    setBusy(true); setError("");
    try {
      const next = library.versions.filter((item) => item.skill_id === skillId)
        .reduce((max, item) => Math.max(max, item.version), 0) + 1;
      await saveProjectSkill(projectId, { skill_id: skillId, version: next, content });
      await reload();
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  };
  const toggle = async (id: string, version: number, active: boolean) => {
    setBusy(true); setError("");
    try {
      if (active) await deactivateProjectSkill(projectId, id);
      else await activateProjectSkill(projectId, id, version);
      await reload();
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  };
  return <section className="skill-library" aria-label="项目技能库">
    <header><strong>项目 Skill Library</strong><small>只由作者保存和显式启用；启用后在下一轮编辑会话生效。</small></header>
    <label>技能 ID<input value={skillId} onChange={(e) => { setSkillId(e.target.value); }} /></label>
    <label>Markdown<textarea value={content} onChange={(e) => setContent(e.target.value)} rows={8} /></label>
    <button onClick={() => void save()} disabled={busy}>保存作者版本</button>
    {error && <p className="document-error">{error}</p>}
    <h4>编辑提议（未自动启用）</h4>
    {library.proposals.length === 0 ? <small>暂无待确认提议。</small> : library.proposals.map((proposal) =>
      <article key={proposal.proposal_id}><strong>{proposal.skill.skill_id}</strong><p>{proposal.purpose}</p><small>{proposal.behavior_impact} · 状态：{proposal.status}</small></article>)}
    <h4>已保存版本</h4>
    {library.versions.length === 0 ? <small>暂无技能版本。</small> : library.versions.map((skill) => {
      const active = enabled.has(`${skill.skill_id}:${skill.version}`);
      return <article key={`${skill.skill_id}:${skill.version}`} className="skill-entry">
        <div><strong>{skill.skill_id} v{skill.version}</strong><small>{skill.source} · {active ? "已启用" : "未启用"}</small></div>
        <button onClick={() => void toggle(skill.skill_id, skill.version, active)} disabled={busy}>{active ? "停用技能" : "启用技能"}</button>
      </article>;
    })}
  </section>;
}
