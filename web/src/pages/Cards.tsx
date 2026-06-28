import { useEffect, useState } from "react";
import { Table, Tag, Typography, Spin, Empty } from "antd";
import { listCards, Card } from "../api/client";

const { Text } = Typography;

export default function Cards() {
  const [cards, setCards] = useState<Card[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listCards()
      .then(setCards)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Spin size="large" style={{ display: "block", margin: "100px auto" }} />;
  if (!cards.length) return <Empty description="暂无角色卡" />;

  const columns = [
    {
      title: "卡片名称",
      dataIndex: "name",
      key: "name",
      render: (n: string) => <Text strong>{n}</Text>,
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      render: (s: string) => <Tag color={s === "ready" ? "green" : "orange"}>{s}</Tag>,
    },
    {
      title: "开场白",
      dataIndex: "greeting_count",
      key: "greeting_count",
    },
    {
      title: "世界书条目",
      dataIndex: "worldbook_count",
      key: "worldbook_count",
    },
    {
      title: "导入时间",
      dataIndex: "created_at",
      key: "created_at",
      render: (t: string) => new Date(t).toLocaleString("zh-CN"),
    },
  ];

  return (
    <div>
      <Text strong style={{ fontSize: 18, display: "block", marginBottom: 16 }}>
        角色卡列表
      </Text>
      <Table
        dataSource={cards}
        columns={columns}
        rowKey="card_id"
        pagination={false}
      />
    </div>
  );
}
