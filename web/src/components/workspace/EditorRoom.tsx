import { useMemo, useState, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { useEditorSocket } from "../../hooks/useEditorSocket";
import { MessageComposer } from "./MessageComposer";
import { MessageCard } from "./MessageCard";
import { AuthorPlanCard } from "./AuthorPlanCard";
import { PipelineTimeline } from "./PipelineTimeline";
import { ToolActivity } from "./ToolActivity";
import { ConversationToolbar } from "./ConversationToolbar";
import { ProjectFilePicker } from "./ProjectFilePicker";
import "./EditorRoom.css";

interface Props {
  projectId: string;
  room: string;
  branchId?: string;
  onBranchChange?: (branchId: string) => void;
}

export function EditorRoom({ projectId, room, branchId = "main", onBranchChange }: Props) {
  const { state, status, send } = useEditorSocket({ projectId, room, branchId });
  const partialMessages = useMemo(() => Object.entries(state.partial), [state.partial]);
  const [references, setReferences] = useState<string[]>([]);

  const action = (type: string, plan: Record<string, any>) =>
    send({ type, plan_id: plan.plan_id, revision: plan.revision });
  const decideTool = (approvalId: string, decision: "allow" | "deny", remember: boolean) =>
    send({ type: "tool_approval_decision", approval_id: approvalId, decision, remember });

  const handleSend = useCallback((text: string) => {
    const frame: Record<string, unknown> = {
      type: "author_message",
      client_message_id: crypto.randomUUID(),
      text,
    };
    if (references.length > 0) {
      frame.references = references.map((path) => ({ path }));
    }
    send(frame);
    setReferences([]);
  }, [send, references]);

  const handleFork = useCallback(async (parentId: string, forkEventId: number, title: string) => {
    const { createConversation } = await import("../../api/workspace");
    try {
      const branch = await createConversation(projectId, room, {
        parent_branch_id: parentId,
        fork_event_id: forkEventId,
        title,
      });
      onBranchChange?.(branch.branch_id);
    } catch { /* ignore */ }
  }, [projectId, room, onBranchChange]);

  return (
    <main
      className="editor-room"
      aria-label={room === "book" ? "全书编辑对话" : `${room.replace("chapter:", "第")}章编辑对话`}
    >
      <div className="connection-state">
        <span className={`status-dot ${status}`} />
        {status === "connected" ? "编辑在线" : "正在重连"}
      </div>

      <ConversationToolbar
        projectId={projectId}
        room={room}
        selectedBranchId={branchId}
        onSelect={(bid) => onBranchChange?.(bid)}
        onNew={async () => {
          const { createConversation } = await import("../../api/workspace");
          try {
            const branch = await createConversation(projectId, room, { title: "新对话" });
            onBranchChange?.(branch.branch_id);
          } catch { /* ignore */ }
        }}
        onFork={handleFork}
        busy={status !== "connected"}
      />

      <div className="message-scroll">
        {!state.messages.length && !partialMessages.length && (
          <div className="editor-welcome">
            <span>编辑室</span>
            <h1>先把你脑子里的东西都倒出来。</h1>
            <p>我会追问、质疑和帮你补足，但不会替你选剧情。计划只有在你明确确认后，才会进入写作管线。</p>
          </div>
        )}

        {state.messages.map((message) => {
          const turnStatus = message.turnId ? state.turns[message.turnId]?.status : undefined;
          return (
            <MessageCard
              key={message.id}
              message={message}
              turnStatus={turnStatus}
              onCopy={(text) => navigator.clipboard.writeText(text).catch(() => {})}
              onEdit={
                message.role === "author"
                  ? () => {
                      // preload composer text, then fork and resend
                    }
                  : undefined
              }
              onRegenerate={
                message.role === "editor"
                  ? () => {
                      // fork and resend original author message
                    }
                  : undefined
              }
              onRetry={
                turnStatus && ["failed", "interrupted", "cancelled"].includes(turnStatus)
                  ? () => {
                      // retry the turn
                    }
                  : undefined
              }
            />
          );
        })}

        {partialMessages.map(([messageId, text]) => (
          <article
            className="message editor streaming"
            key={messageId}
            aria-label="编辑正在回应"
            data-message-id={messageId}
          >
            <div>编辑 · 正在回应</div>
            <p>{text}<span className="cursor" /></p>
          </article>
        ))}

        {Object.values(state.plans).map((plan) => (
          <AuthorPlanCard
            key={plan.plan_id}
            plan={plan}
            onApprove={() => action("approve_plan", plan)}
            onExecute={() => action("execute_plan", plan)}
          />
        ))}

        <PipelineTimeline steps={state.pipeline} />
        {state.writerBuffer && (
          <article className="writer-stream">
            <div>Writer · 实时正文</div>
            <p>{state.writerBuffer}</p>
          </article>
        )}
        {state.errors.map((error, index) => (
          <div className="event-error" key={`${error}-${index}`}>{error}</div>
        ))}
      </div>

      <ToolActivity
        activity={state.toolActivity}
        approvals={state.pendingApprovals}
        onDecision={decideTool}
      />

      <div className="composer-row">
        <ProjectFilePicker
          projectId={projectId}
          selected={references}
          onSelect={(path) => setReferences((prev) => [...prev, path])}
          onRemove={(path) => setReferences((prev) => prev.filter((p) => p !== path))}
        />
        <MessageComposer
          storageKey={`novel-draft:${projectId}:${room}:${branchId}`}
          disabled={status !== "connected"}
          onSend={handleSend}
          onCancel={() => send({ type: "cancel" })}
        />
      </div>
    </main>
  );
}
