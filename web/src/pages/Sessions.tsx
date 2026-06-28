import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { List, Typography, Tag, Spin, Empty } from "antd";
import { MessageOutlined } from "@ant-design/icons";
import { listSessions, Session } from "../api/client";

const { Text } = Typography;

export default function Sessions() {
  const navigate = useNavigate();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listSessions()
      .then(setSessions)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Spin size="large" style={{ display: "block", margin: "100px auto" }} />;
  if (!sessions.length) return <Empty description="暂无会话记录" />;

  return (
    <List
      header={<Text strong style={{ fontSize: 18 }}>会话列表</Text>}
      dataSource={sessions}
      renderItem={(s) => (
        <List.Item
          onClick={() => navigate(`/sessions/${s.session_id}`)}
          style={{ cursor: "pointer", padding: "12px 16px" }}
          extra={<Tag>{s.turn_count} 回合</Tag>}
        >
          <List.Item.Meta
            avatar={<MessageOutlined style={{ fontSize: 24, color: "#1677ff" }} />}
            title={s.card_name}
            description={
              <>
                <Text type="secondary">ID: {s.session_id.slice(0, 16)}…</Text>
                <br />
                <Text type="secondary">greeting: {s.greeting_id}</Text>
                <br />
                <Text type="secondary">
                  {new Date(s.last_turn_time || s.created_at).toLocaleString("zh-CN")}
                </Text>
              </>
            }
          />
        </List.Item>
      )}
    />
  );
}
