import { useEffect, useState, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Button, Spin, Empty, Tag, Typography, message } from "antd";
import { ArrowLeftOutlined, PlayCircleOutlined } from "@ant-design/icons";
import { getSession, listTurns, continueSession, Turn } from "../api/client";

const { Text } = Typography;

export default function SessionChat() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const bottomRef = useRef<HTMLDivElement>(null);
  const [session, setSession] = useState<any>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [loading, setLoading] = useState(true);
  const [continuing, setContinuing] = useState(false);

  const load = () => {
    if (!id) return;
    setLoading(true);
    Promise.all([getSession(id), listTurns(id)])
      .then(([s, t]) => {
        setSession(s);
        setTurns(t);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [id]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  const handleContinue = async () => {
    if (!id) return;
    setContinuing(true);
    try {
      const result = await continueSession(id);
      if (result.success) {
        message.success(`续写完成: Turn ${result.turn_index}`);
        load();
      } else {
        message.error("续写失败");
      }
    } catch (e: any) {
      message.error(e.message);
    }
    setContinuing(false);
  };

  if (loading) return <Spin size="large" style={{ display: "block", margin: "100px auto" }} />;
  if (!session) return <Empty description="会话不存在" />;

  return (
    <div style={{ maxWidth: 800, margin: "0 auto" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate("/sessions")} />
        <Text strong style={{ fontSize: 18, flex: 1 }}>{session.card_name}</Text>
        <Button
          type="primary"
          icon={<PlayCircleOutlined />}
          loading={continuing}
          onClick={handleContinue}
        >
          续写
        </Button>
      </div>
      <Text type="secondary" style={{ display: "block", marginBottom: 16 }}>
        ID: {session.session_id} · greeting: {session.greeting_id} · {session.turn_count} 回合
      </Text>

      {/* Opening */}
      {session.opening_content && (
        <div style={{
          background: "#e6f4ff", border: "1px solid #91caff",
          borderRadius: 8, padding: "12px 16px", marginBottom: 16,
          whiteSpace: "pre-wrap",
        }}>
          <Text type="secondary" style={{ fontSize: 12 }}>开场白 ({session.greeting_id})</Text>
          <div style={{ marginTop: 4 }}>{session.opening_content}</div>
        </div>
      )}

      {/* Turns */}
      {turns.map((t) => (
        <div key={t.turn_id} style={{ marginBottom: 20 }}>
          <div style={{
            textAlign: "center", marginBottom: 8, fontSize: 12, color: "#999",
          }}>
            Turn {t.turn_index} · {new Date(t.accepted_at || t.created_at).toLocaleString("zh-CN")}
          </div>

          {/* Player input (right-aligned) */}
          {t.player_input && (
            <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 8 }}>
              <div style={{
                background: "#f0f0f0", borderRadius: "12px 12px 4px 12px",
                padding: "10px 14px", maxWidth: "70%", whiteSpace: "pre-wrap",
              }}>
                <div style={{ fontSize: 12, color: "#999", marginBottom: 2 }}>玩家</div>
                {t.player_input}
              </div>
            </div>
          )}

          {/* Writer output (left-aligned) */}
          {t.writer_output && (
            <div style={{ display: "flex", justifyContent: "flex-start", marginBottom: 8 }}>
              <div style={{
                background: "#e6f4ff", borderRadius: "12px 12px 12px 4px",
                padding: "10px 14px", maxWidth: "70%", whiteSpace: "pre-wrap",
              }}>
                <div style={{ fontSize: 12, color: "#1677ff", marginBottom: 2 }}>Writer</div>
                {t.writer_output}
              </div>
            </div>
          )}

          {/* Mode tag */}
          <div style={{ textAlign: "center" }}>
            {t.mode === "continue" && <Tag color="purple">Continue</Tag>}
            {t.writer_output && t.writer_output.length < 1000 && (
              <Tag color="orange">字数不足</Tag>
            )}
          </div>
        </div>
      ))}

      <div ref={bottomRef} />
    </div>
  );
}
