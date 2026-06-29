import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Button, Empty, Input, Spin, Tag, Typography, message } from "antd";
import { ArrowLeftOutlined, PlayCircleOutlined, SendOutlined } from "@ant-design/icons";
import {
  continueSessionV2,
  getSession,
  listTurns,
  sendTurn,
  Session,
  Turn,
} from "../api/client";
import PresetViewer from "../components/PresetViewer";
import WorkflowSelector from "../components/WorkflowSelector";

const { Text } = Typography;

type SessionDetails = Session & { opening_content?: string };

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export default function SessionChat() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const bottomRef = useRef<HTMLDivElement>(null);
  const [session, setSession] = useState<SessionDetails | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [loading, setLoading] = useState(true);
  const [continuing, setContinuing] = useState(false);
  const [sending, setSending] = useState(false);
  const [inputText, setInputText] = useState("");
  const [mode, setMode] = useState("hybrid");
  const [workflow, setWorkflow] = useState("");

  const load = () => {
    if (!id) return;
    setLoading(true);
    Promise.all([getSession(id), listTurns(id)])
      .then(([sessionDetails, turnList]) => {
        setSession(sessionDetails);
        setTurns(turnList);
      })
      .catch((error) => message.error(getErrorMessage(error)))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, [id]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  const executionOptions = {
    mode,
    workflow: workflow || undefined,
  };

  const handleContinue = async () => {
    if (!id) return;
    setContinuing(true);
    try {
      const result = await continueSessionV2(id, executionOptions);
      if (result.success) {
        message.success(`Continue complete: turn ${result.turn_index ?? ""}`.trim());
        load();
      } else {
        message.error("Continue failed");
      }
    } catch (error) {
      message.error(getErrorMessage(error));
    } finally {
      setContinuing(false);
    }
  };

  const handleSend = async () => {
    if (!id || !inputText.trim()) return;
    setSending(true);
    try {
      const result = await sendTurn(id, inputText.trim(), executionOptions);
      if (result.success) {
        setInputText("");
        load();
      } else {
        message.error("Send failed");
      }
    } catch (error) {
      message.error(getErrorMessage(error));
    } finally {
      setSending(false);
    }
  };

  if (loading) {
    return <Spin size="large" style={{ display: "block", margin: "100px auto" }} />;
  }

  if (!session) {
    return <Empty description="Session not found" />;
  }

  return (
    <div style={{ maxWidth: 860, margin: "0 auto" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate("/sessions")} />
        <Text strong style={{ fontSize: 18, flex: 1 }}>
          {session.card_name}
        </Text>
        <Button
          type="primary"
          icon={<PlayCircleOutlined />}
          loading={continuing}
          onClick={handleContinue}
        >
          Continue
        </Button>
      </div>

      <Text type="secondary" style={{ display: "block", marginBottom: 12 }}>
        ID: {session.session_id} | greeting: {session.greeting_id} | {session.turn_count} turns
      </Text>

      <div style={{ marginBottom: 12 }}>
        <WorkflowSelector
          action="turn"
          mode={mode}
          workflow={workflow}
          onModeChange={setMode}
          onWorkflowChange={setWorkflow}
        />
        <PresetViewer />
      </div>

      {session.opening_content && (
        <div
          style={{
            background: "#e6f4ff",
            border: "1px solid #91caff",
            borderRadius: 8,
            padding: "12px 16px",
            marginBottom: 16,
            whiteSpace: "pre-wrap",
          }}
        >
          <Text type="secondary" style={{ fontSize: 12 }}>
            Opening ({session.greeting_id})
          </Text>
          <div style={{ marginTop: 4 }}>{session.opening_content}</div>
        </div>
      )}

      {turns.map((turn) => (
        <div key={turn.turn_id} style={{ marginBottom: 20 }}>
          <div style={{ textAlign: "center", marginBottom: 8, fontSize: 12, color: "#999" }}>
            Turn {turn.turn_index} |{" "}
            {new Date(turn.accepted_at || turn.created_at).toLocaleString("zh-CN")}
          </div>

          {turn.player_input && (
            <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 8 }}>
              <div
                style={{
                  background: "#f0f0f0",
                  borderRadius: "12px 12px 4px 12px",
                  padding: "10px 14px",
                  maxWidth: "72%",
                  whiteSpace: "pre-wrap",
                }}
              >
                <div style={{ fontSize: 12, color: "#999", marginBottom: 2 }}>Player</div>
                {turn.player_input}
              </div>
            </div>
          )}

          {turn.writer_output && (
            <div style={{ display: "flex", justifyContent: "flex-start", marginBottom: 8 }}>
              <div
                style={{
                  background: "#e6f4ff",
                  borderRadius: "12px 12px 12px 4px",
                  padding: "10px 14px",
                  maxWidth: "72%",
                  whiteSpace: "pre-wrap",
                }}
              >
                <div style={{ fontSize: 12, color: "#1677ff", marginBottom: 2 }}>Writer</div>
                {turn.writer_output}
              </div>
            </div>
          )}

          <div style={{ textAlign: "center" }}>
            {turn.mode === "continue" && <Tag color="purple">Continue</Tag>}
            {turn.writer_output && turn.writer_output.length < 1000 && (
              <Tag color="orange">Short output</Tag>
            )}
          </div>
        </div>
      ))}

      <div
        style={{
          display: "flex",
          gap: 8,
          marginTop: 16,
          padding: "12px 0 4px",
          position: "sticky",
          bottom: 0,
          background: "#f5f5f5",
        }}
      >
        <Input.TextArea
          autoSize={{ minRows: 1, maxRows: 4 }}
          placeholder="Enter player message"
          value={inputText}
          onChange={(event) => setInputText(event.target.value)}
          onPressEnter={(event) => {
            if (!event.shiftKey) {
              event.preventDefault();
              handleSend();
            }
          }}
        />
        <Button type="primary" icon={<SendOutlined />} loading={sending} onClick={handleSend}>
          Send
        </Button>
      </div>

      <div ref={bottomRef} />
    </div>
  );
}
