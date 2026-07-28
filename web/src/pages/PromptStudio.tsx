import { useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ApiConflictError, getPrompt, listPrompts, PromptResource, promptDiff, savePrompt } from "../api/workspace";
import { getLlmConfig, listLlmModels, testLlmConnection, updateLlmConfig, LlmConfig, LlmRoleOverride } from "../api/client";
import "./PromptStudio.css";

const ROLE_LABELS: Record<string, string> = {
  brain: "编辑器 (brain)",
  architect: "大纲 (architect)",
  director: "导演 (director)",
  writer: "写手 (writer)",
  continuity_checker: "连续性 (continuity_checker)",
  style_cleaner: "风格清洗 (style_cleaner)",
  ledger_curator: "账本 (ledger_curator)",
  npc_planner: "NPC规划 (npc_planner)",
};

const LOCAL_PROVIDERS: Array<{ id: string; label: string; defaultBase: string; defaultKeyEnv: string }> = [
  { id: "deepseek", label: "DeepSeek", defaultBase: "https://api.deepseek.com/v1", defaultKeyEnv: "DEEPSEEK_API_KEY" },
  { id: "opencode", label: "OpenCode", defaultBase: "https://opencode.ai/zen/go/v1", defaultKeyEnv: "OPENCODE_API_KEY" },
  { id: "mimo", label: "小米 MiMo", defaultBase: "https://token-plan-cn.xiaomimimo.com/v1", defaultKeyEnv: "MIMO_API_KEY" },
  { id: "siliconflow", label: "硅基流动", defaultBase: "https://api.siliconflow.cn/v1", defaultKeyEnv: "SILICONFLOW_API_KEY" },
  { id: "openai-compatible", label: "自定义 OpenAI 兼容", defaultBase: "", defaultKeyEnv: "" },
];

type Tab = "prompts" | "llm";

export default function PromptStudio() {
  const { id = "" } = useParams(); const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedTab: Tab = searchParams.get("tab") === "llm" ? "llm" : "prompts";
  const [tab, setTab] = useState<Tab>(requestedTab);
  useEffect(() => { setTab(requestedTab); }, [requestedTab]);
  const selectTab = (next: Tab) => {
    setTab(next);
    setSearchParams({ tab: next });
  };

  // Prompt tab state
  const [roles, setRoles] = useState<PromptResource[]>([]); const [role, setRole] = useState("editor");
  const [prompt, setPrompt] = useState<PromptResource | null>(null); const [buffer, setBuffer] = useState("");
  const [editing, setEditing] = useState(false); const [diff, setDiff] = useState(""); const [error, setError] = useState("");
  useEffect(() => { listPrompts(id).then(setRoles).catch((e) => setError(String(e))); }, [id]);
  useEffect(() => { if (tab === "prompts") { getPrompt(id, role).then((p) => { setPrompt(p); setBuffer(p.content); setEditing(false); setError(""); }); } }, [id, role, tab]);
  const save = async () => {
    if (!prompt) return;
    try { const next = await savePrompt(id, role, buffer, prompt.revision); setPrompt(next); setEditing(false); }
    catch (e) { setError(e instanceof ApiConflictError ? `版本冲突：服务器当前为 v${e.currentRevision}` : String(e)); }
  };

  // LLM config state
  const [llmConfig, setLlmConfig] = useState<LlmConfig | null>(null);
  const [llmEditing, setLlmEditing] = useState(false);
  const [llmOverrides, setLlmOverrides] = useState<Record<string, LlmRoleOverride>>({});
  const [llmSelectedRole, setLlmSelectedRole] = useState("brain");
  const [llmSaving, setLlmSaving] = useState(false);
  const [llmConnectionStatus, setLlmConnectionStatus] = useState("");
  const [llmModels, setLlmModels] = useState<string[]>([]);
  const [llmChecking, setLlmChecking] = useState(false);

  useEffect(() => {
    if (tab === "llm") {
      getLlmConfig(id).then((cfg) => {
        setLlmConfig(cfg);
        setLlmOverrides(JSON.parse(JSON.stringify(cfg.overrides)));
        setError("");
      }).catch((e) => setError(String(e)));
    }
  }, [id, tab]);

  const saveLlm = async () => {
    setLlmSaving(true);
    try {
      const result = await updateLlmConfig(id, llmOverrides);
      setLlmConfig((prev) => prev ? { ...prev, overrides: result.overrides } : null);
      setLlmEditing(false);
      setError("");
    } catch (e) { setError(String(e)); }
    finally { setLlmSaving(false); }
  };

  const persistLlmOverrides = async () => {
    const result = await updateLlmConfig(id, llmOverrides);
    setLlmConfig((prev) => prev ? { ...prev, overrides: result.overrides } : null);
  };

  const updateOverride = (role: string, field: string, value: string | number | undefined) => {
    setLlmOverrides((prev) => {
      const next = { ...prev };
      const current = { ...(next[role] || {}) };
      if (value === undefined || value === "" || value === 0) {
        delete (current as Record<string, unknown>)[field];
        if (Object.keys(current).length === 0) {
          delete next[role];
        } else {
          next[role] = current;
        }
      } else {
        (current as Record<string, unknown>)[field] = value;
        next[role] = current;
      }
      return next;
    });
  };

  const roleOverride = (role: string): LlmRoleOverride & { _default: LlmRoleOverride } => {
    const def = llmConfig?.defaults[role] || {};
    const ovr = llmOverrides[role] || {};
    return { ...def, ...ovr, _default: def };
  };

  const hasOverrides = (role: string) => {
    return llmOverrides[role] && Object.keys(llmOverrides[role]).length > 0;
  };

  const testConnection = async () => {
    setLlmChecking(true);
    setLlmConnectionStatus("");
    try {
      const result = await testLlmConnection(id, llmSelectedRole, roleOverride(llmSelectedRole));
      setLlmConnectionStatus(`连接成功，可读取 ${result.model_count} 个模型。`);
    } catch (e) {
      setLlmConnectionStatus(`连接失败：${String(e)}`);
    } finally {
      setLlmChecking(false);
    }
  };

  const discoverModels = async () => {
    setLlmChecking(true);
    setLlmConnectionStatus("");
    try {
      const result = await listLlmModels(id, llmSelectedRole, roleOverride(llmSelectedRole));
      setLlmModels(result.models);
      await persistLlmOverrides();
      setLlmConnectionStatus(`已获取 ${result.models.length} 个模型。`);
    } catch (e) {
      setLlmConnectionStatus(`获取模型失败：${String(e)}`);
    } finally {
      setLlmChecking(false);
    }
  };

  return <div className="prompt-studio">
    <aside>
      <button className="back" onClick={() => navigate(`/novels/${id}/workspace/book`)}>← 返回写作区</button>
      <h2>Prompt Studio</h2>
      <p>调整专属写作 AI 的角色提示词与模型配置。</p>
      <button className={tab === "prompts" ? "selected" : ""} onClick={() => selectTab("prompts")}>
        <strong>角色提示词</strong>
      </button>
      <button className={tab === "llm" ? "selected" : ""} onClick={() => selectTab("llm")}>
        <strong>LLM 模型配置</strong><small>供应商、模型、参数</small>
      </button>
      {tab === "prompts" && <>
        <hr style={{ margin: "12px 8px", border: "none", borderTop: "1px solid var(--border)" }} />
        {roles.map((item) => <button className={item.role === role ? "selected" : ""} key={item.role} onClick={() => setRole(item.role)}>
          <strong>{item.role}</strong><small>{item.source === "system" ? "系统默认" : `项目 v${item.revision}`}</small>
        </button>)}
      </>}
      {tab === "llm" && <>
        <hr style={{ margin: "12px 8px", border: "none", borderTop: "1px solid var(--border)" }} />
        {Object.keys(ROLE_LABELS).map((roleKey) => (
          <button
            key={roleKey}
            className={llmSelectedRole === roleKey ? "selected" : ""}
            onClick={() => setLlmSelectedRole(roleKey)}
          >
            <strong>{ROLE_LABELS[roleKey] || roleKey}</strong>
            <small>供应商：{roleOverride(roleKey).provider || "—"}{hasOverrides(roleKey) ? " · 已自定义" : ""}</small>
          </button>
        ))}
      </>}
    </aside>
    <main>
      {tab === "prompts" && <>
        <header><div><span>{prompt?.source === "system" ? "系统 Prompt" : "项目覆盖"}</span><h1>{role}</h1></div>
          <div><button className="quiet-button" onClick={async () => setDiff((await promptDiff(id, role)).diff)}>对比系统版</button>
            {!editing ? <button className="primary-button" onClick={() => setEditing(true)}>编辑项目版本</button> :
            <><button className="quiet-button" onClick={() => { setEditing(false); setBuffer(prompt?.content ?? ""); }}>取消</button><button className="primary-button" onClick={save}>保存为新版本</button></>}</div>
        </header>
        <div className="snapshot-notice">修改只影响之后启动的任务。正在运行的任务继续使用启动时冻结的 Prompt 快照。</div>
        {error && <div className="prompt-error">{error}</div>}
        {editing ? <textarea value={buffer} onChange={(e) => setBuffer(e.target.value)} /> : <pre>{prompt?.content}</pre>}
        {diff && <section className="prompt-diff"><div>与系统版本的差异</div><pre>{diff || "没有差异"}</pre></section>}
      </>}

      {tab === "llm" && <>
        <header>
          <div><span>LLM 模型配置</span><h1>{ROLE_LABELS[llmSelectedRole] || llmSelectedRole}</h1></div>
          <div>
            {!llmEditing ? <button className="primary-button" onClick={() => setLlmEditing(true)}>编辑配置</button> :
            <><button className="quiet-button" onClick={() => { setLlmEditing(false); setLlmOverrides(JSON.parse(JSON.stringify(llmConfig?.overrides || {}))); }}>取消</button>
            <button className="primary-button" onClick={saveLlm} disabled={llmSaving}>{llmSaving ? "保存中…" : "保存配置"}</button></>}
          </div>
        </header>
        <div className="snapshot-notice">修改 LLM 配置后需刷新页面或重启编辑会话才会对新消息生效。正在运行的任务不受影响。</div>
        {error && <div className="prompt-error">{error}</div>}

        {llmEditing ? <LlmRoleEditor
          cfg={roleOverride(llmSelectedRole)}
          onChange={(field, value) => updateOverride(llmSelectedRole, field, value)}
          onTestConnection={testConnection}
          onDiscoverModels={discoverModels}
          models={llmModels}
          busy={llmChecking}
          connectionStatus={llmConnectionStatus}
        /> : <LlmRoleView cfg={roleOverride(llmSelectedRole)} />}
      </>}
    </main>
  </div>;
}

function LlmRoleView({ cfg }: { cfg: LlmRoleOverride & { _default: LlmRoleOverride } }) {
  return <div className="llm-config-view">
    <table>
      <tbody>
        <tr><td>供应商</td><td>{cfg.provider || cfg._default.provider || "—"}{cfg.provider && cfg.provider !== cfg._default.provider ? <mark>已覆盖</mark> : null}</td></tr>
        <tr><td>模型</td><td>{cfg.model || cfg._default.model || "—"}{cfg.model && cfg.model !== cfg._default.model ? <mark>已覆盖</mark> : null}</td></tr>
        <tr><td>最大 Token</td><td>{cfg.max_tokens ?? cfg._default.max_tokens ?? "—"}{cfg.max_tokens && cfg.max_tokens !== cfg._default.max_tokens ? <mark>已覆盖</mark> : null}</td></tr>
        <tr><td>思考等级</td><td>{cfg.thinking_level || cfg._default.thinking_level || "off"}{cfg.thinking_level && cfg.thinking_level !== cfg._default.thinking_level ? <mark>已覆盖</mark> : null}</td></tr>
        <tr><td>API 地址</td><td>{cfg.api_base || "使用默认"}</td></tr>
        <tr><td>密钥来源</td><td>{cfg.api_key_env || cfg.api_key || "使用默认"}</td></tr>
      </tbody>
    </table>
  </div>;
}

function LlmRoleEditor({ cfg, onChange, onTestConnection, onDiscoverModels, models, busy, connectionStatus }: {
  cfg: LlmRoleOverride & { _default: LlmRoleOverride };
  onChange: (field: string, value: string | number | undefined) => void;
  onTestConnection: () => void;
  onDiscoverModels: () => void;
  models: string[];
  busy: boolean;
  connectionStatus: string;
}) {
  const providerOptions = LOCAL_PROVIDERS;
  const selectedProvider = cfg.provider || cfg._default.provider || "";
  const isCustom = selectedProvider === "openai-compatible" || !providerOptions.some(p => p.id === selectedProvider);

  return <div className="llm-config-editor">
    <div className="llm-field">
      <label>供应商</label>
      <select value={isCustom ? "openai-compatible" : selectedProvider} onChange={(e) => {
        const v = e.target.value;
        if (v === "openai-compatible") {
          onChange("provider", "openai-compatible");
        } else {
          const p = providerOptions.find(x => x.id === v);
          if (p) {
            onChange("provider", p.id === cfg._default.provider ? undefined : p.id);
            // Only set api_base and api_key_env if they differ from defaults
            // Don't auto-set to avoid cluttering overrides
          }
        }
      }}>
        {providerOptions.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
      </select>
    </div>
    <div className="llm-connection-actions">
      <button className="quiet-button" type="button" disabled={busy} onClick={onTestConnection}>测试连接</button>
      <button className="quiet-button" type="button" disabled={busy} onClick={onDiscoverModels}>获取模型列表</button>
      {connectionStatus && <span role="status">{connectionStatus}</span>}
    </div>
    <div className="llm-field">
      <label>API Base URL <small>{cfg._default.provider ? `默认: ${LOCAL_PROVIDERS.find(p => p.id === cfg._default.provider)?.defaultBase || "—"}` : ""}</small></label>
      <input type="text" value={cfg.api_base || ""} placeholder={selectedProvider && !isCustom ? LOCAL_PROVIDERS.find(p => p.id === selectedProvider)?.defaultBase || "" : ""} onChange={(e) => onChange("api_base", e.target.value || undefined)} />
    </div>
    <div className="llm-field">
      <label>密钥环境变量或直接 Key <small>{cfg._default.provider ? `默认: ${LOCAL_PROVIDERS.find(p => p.id === cfg._default.provider)?.defaultKeyEnv || "—"}` : ""}</small></label>
      <input type="text" value={cfg.api_key ?? cfg.api_key_env ?? ""} placeholder={selectedProvider && !isCustom ? LOCAL_PROVIDERS.find(p => p.id === selectedProvider)?.defaultKeyEnv || "" : ""} onChange={(e) => onChange("api_key", e.target.value || undefined)} />
    </div>
    <div className="llm-field">
      <label>模型 ID <small>{cfg._default.model ? `默认: ${cfg._default.model}` : ""}</small></label>
      <input type="text" value={cfg.model || ""} placeholder={cfg._default.model || ""} onChange={(e) => onChange("model", e.target.value || undefined)} />
      {models.length > 0 && <select aria-label="已发现模型" defaultValue="" onChange={(e) => onChange("model", e.target.value || undefined)}>
        <option value="" disabled>选择已发现模型</option>
        {models.map((model) => <option key={model} value={model}>{model}</option>)}
      </select>}
    </div>
    <div className="llm-field">
      <label>最大 Token <small>{cfg._default.max_tokens ? `默认: ${cfg._default.max_tokens}` : ""}</small></label>
      <input type="number" min={100} max={100000} step={100} value={cfg.max_tokens ?? ""} placeholder={String(cfg._default.max_tokens ?? 4000)} onChange={(e) => onChange("max_tokens", e.target.value ? Number(e.target.value) : undefined)} />
    </div>
    <div className="llm-field">
      <label>思考等级</label>
      <select value={cfg.thinking_level || cfg._default.thinking_level || "off"} onChange={(e) => onChange("thinking_level", e.target.value === cfg._default.thinking_level ? undefined : e.target.value)}>
        <option value="off">关闭</option>
        <option value="low">低</option>
        <option value="medium">中</option>
        <option value="high">高</option>
      </select>
    </div>
  </div>;
}
