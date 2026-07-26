import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { applyEditorEvent, EditorEvent, emptyEditorState } from "../state/editorEvents";

export function useEditorSocket({ projectId, room }: { projectId: string; room: string }) {
  const [state, dispatch] = useReducer(applyEditorEvent, undefined, emptyEditorState);
  const [status, setStatus] = useState<"connecting" | "connected" | "reconnecting" | "closed">("connecting");
  const socket = useRef<WebSocket | null>(null);
  const lastId = useRef(0);
  const reconnect = useRef(0);
  useEffect(() => { lastId.current = state.lastEventId; }, [state.lastEventId]);
  useEffect(() => {
    let stopped = false; let timer = 0;
    const open = () => {
      if (stopped) return;
      setStatus(reconnect.current ? "reconnecting" : "connecting");
      const protocol = location.protocol === "https:" ? "wss:" : "ws:";
      const ws = new WebSocket(`${protocol}//${location.host}/awp/ws/v1/novels/${encodeURIComponent(projectId)}/editor/${encodeURIComponent(room)}`);
      socket.current = ws;
      ws.onopen = () => {
        reconnect.current = 0; setStatus("connected");
        ws.send(JSON.stringify({ type: "resume_from", event_id: lastId.current }));
      };
      ws.onmessage = (message) => {
        const event = JSON.parse(message.data) as EditorEvent;
        dispatch(event);
      };
      ws.onclose = () => {
        if (stopped) return;
        reconnect.current += 1; setStatus("reconnecting");
        timer = window.setTimeout(open, Math.min(10000, 500 * 2 ** reconnect.current));
      };
    };
    open();
    return () => { stopped = true; window.clearTimeout(timer); socket.current?.close(); setStatus("closed"); };
  }, [projectId, room]);
  const send = useCallback((frame: Record<string, unknown>) => {
    if (!socket.current || socket.current.readyState !== WebSocket.OPEN) throw new Error("编辑室尚未连接");
    socket.current.send(JSON.stringify(frame));
  }, []);
  return { state, status, send };
}
