import { useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { EditorMessage } from "../../state/editorEvents";

interface Props {
  message: EditorMessage;
  turnStatus?: string;
  onCopy?: (text: string) => void;
  onEdit?: () => void;
  onRegenerate?: () => void;
  onRetry?: () => void;
}

export function MessageCard({ message, turnStatus, onCopy, onEdit, onRegenerate, onRetry }: Props) {
  const isAuthor = message.role === "author";
  const isCompleted = turnStatus === "completed";
  const isTerminal = ["failed", "interrupted", "cancelled"].includes(turnStatus ?? "");

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(message.text);
    } catch {
      // Fallback silently
    }
  }, [message.text]);

  return (
    <article
      className={`message ${message.role}${message.incomplete ? " incomplete" : ""}`}
      data-event-id={message.eventId}
      data-turn-id={message.turnId}
    >
      <div className="message-header">
        <span className="message-role">{isAuthor ? "你" : "编辑"}</span>
        {message.incomplete && <span className="incomplete-badge">未完成</span>}
        <span className="message-actions">
          <button className="action-btn" onClick={handleCopy} aria-label="复制消息" title="复制">📋</button>
          {isAuthor && onEdit && (
            <button className="action-btn" onClick={onEdit} aria-label="编辑并重新发送" title="编辑重发">✏️</button>
          )}
          {!isAuthor && isCompleted && onRegenerate && (
            <button className="action-btn" onClick={onRegenerate} aria-label="重新生成" title="重新生成">🔄</button>
          )}
          {isTerminal && onRetry && (
            <button className="action-btn retry-btn" onClick={onRetry} aria-label="重试本轮" title="重试本轮">🔁</button>
          )}
        </span>
      </div>
      <div className="message-body">
        {isAuthor ? (
          <pre>{message.text}</pre>
        ) : (
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            skipHtml
            components={{
              a: ({ href, children }) => {
                const isHttp = href?.startsWith("http:") || href?.startsWith("https:");
                return (
                  <a href={href} rel="noreferrer noopener" target={isHttp ? "_blank" : undefined}>
                    {children}
                  </a>
                );
              },
            }}
          >
            {message.text}
          </ReactMarkdown>
        )}
      </div>
    </article>
  );
}
