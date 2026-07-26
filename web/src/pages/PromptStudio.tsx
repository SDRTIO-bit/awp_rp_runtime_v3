import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ApiConflictError, getPrompt, listPrompts, PromptResource, promptDiff, savePrompt } from "../api/workspace";
import "./PromptStudio.css";

export default function PromptStudio() {
  const { id = "" } = useParams(); const navigate = useNavigate();
  const [roles, setRoles] = useState<PromptResource[]>([]); const [role, setRole] = useState("editor");
  const [prompt, setPrompt] = useState<PromptResource | null>(null); const [buffer, setBuffer] = useState("");
  const [editing, setEditing] = useState(false); const [diff, setDiff] = useState(""); const [error, setError] = useState("");
  useEffect(() => { listPrompts(id).then(setRoles).catch((e) => setError(String(e))); }, [id]);
  useEffect(() => { getPrompt(id, role).then((p) => { setPrompt(p); setBuffer(p.content); setEditing(false); setError(""); }); }, [id, role]);
  const save = async () => {
    if (!prompt) return;
    try { const next = await savePrompt(id, role, buffer, prompt.revision); setPrompt(next); setEditing(false); }
    catch (e) { setError(e instanceof ApiConflictError ? `版本冲突：服务器当前为 v${e.currentRevision}` : String(e)); }
  };
  return <div className="prompt-studio">
    <aside><button className="back" onClick={() => navigate(`/novels/${id}/workspace/book`)}>← 返回写作区</button>
      <h2>Prompt Studio</h2><p>调整专属写作 AI 的角色提示词。</p>
      {roles.map((item) => <button className={item.role === role ? "selected" : ""} key={item.role} onClick={() => setRole(item.role)}>
        <strong>{item.role}</strong><small>{item.source === "system" ? "系统默认" : `项目 v${item.revision}`}</small>
      </button>)}
    </aside>
    <main>
      <header><div><span>{prompt?.source === "system" ? "系统 Prompt" : "项目覆盖"}</span><h1>{role}</h1></div>
        <div><button className="quiet-button" onClick={async () => setDiff((await promptDiff(id, role)).diff)}>对比系统版</button>
          {!editing ? <button className="primary-button" onClick={() => setEditing(true)}>编辑项目版本</button> :
          <><button className="quiet-button" onClick={() => { setEditing(false); setBuffer(prompt?.content ?? ""); }}>取消</button><button className="primary-button" onClick={save}>保存为新版本</button></>}</div>
      </header>
      <div className="snapshot-notice">修改只影响之后启动的任务。正在运行的任务继续使用启动时冻结的 Prompt 快照。</div>
      {error && <div className="prompt-error">{error}</div>}
      {editing ? <textarea value={buffer} onChange={(e) => setBuffer(e.target.value)} /> : <pre>{prompt?.content}</pre>}
      {diff && <section className="prompt-diff"><div>与系统版本的差异</div><pre>{diff || "没有差异"}</pre></section>}
    </main>
  </div>;
}
