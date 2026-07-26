import { useMemo } from "react";
import { useEditorSocket } from "../../hooks/useEditorSocket";
import { MessageComposer } from "./MessageComposer";
import { AuthorPlanCard } from "./AuthorPlanCard";
import { PipelineTimeline } from "./PipelineTimeline";
import "./EditorRoom.css";

export function EditorRoom({ projectId, room }: { projectId: string; room: string }) {
  const { state, status, send } = useEditorSocket({ projectId, room });
  const partial = useMemo(() => Object.values(state.partial).join(""), [state.partial]);
  const action = (type: string, plan: Record<string, any>) => send({ type, plan_id: plan.plan_id, revision: plan.revision });
  return <main className="editor-room" aria-label={room === "book" ? "全书编辑对话" : `${room.replace("chapter:", "第")}章编辑对话`}>
    <div className="connection-state"><span className={`status-dot ${status}`} />{status === "connected" ? "编辑在线" : "正在重连，不会自动重发未知状态消息"}</div>
    <div className="message-scroll">
      {!state.messages.length && !partial && <div className="editor-welcome">
        <span>编辑室</span><h1>先把你脑子里的东西都倒出来。</h1>
        <p>我会追问、质疑和帮你补足，但不会替你选剧情。计划只有在你明确确认后，才会进入写作管线。</p>
      </div>}
      {state.messages.map((message) => <article key={message.id} className={`message ${message.role}`}>
        <div>{message.role === "author" ? "你" : "编辑"}</div><p>{message.text}</p>
      </article>)}
      {partial && <article className="message editor streaming"><div>编辑 · 正在回应</div><p>{partial}<span className="cursor" /></p></article>}
      {Object.values(state.plans).map((plan) => <AuthorPlanCard key={plan.plan_id} plan={plan}
        onApprove={() => action("approve_plan", plan)} onExecute={() => action("execute_plan", plan)} />)}
      <PipelineTimeline steps={state.pipeline} />
      {state.writerBuffer && <article className="writer-stream"><div>Writer · 实时正文</div><p>{state.writerBuffer}</p></article>}
      {state.errors.map((error, index) => <div className="event-error" key={`${error}-${index}`}>{error}</div>)}
    </div>
    <MessageComposer storageKey={`novel-draft:${projectId}:${room}`} disabled={status !== "connected"}
      onSend={(text) => send({ type: "author_message", client_message_id: crypto.randomUUID(), text })}
      onCancel={() => send({ type: "cancel" })} />
  </main>;
}
