import { useEffect, useState } from "react";
import {
  Button,
  Drawer,
  Empty,
  Input,
  List,
  Modal,
  Popconfirm,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import { DeleteOutlined, ImportOutlined } from "@ant-design/icons";
import {
  Card,
  deleteCard,
  GreetingInfo,
  importCard,
  listCards,
  listGreetings,
} from "../api/client";

const { Text } = Typography;

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export default function Cards() {
  const [cards, setCards] = useState<Card[]>([]);
  const [loading, setLoading] = useState(true);
  const [importOpen, setImportOpen] = useState(false);
  const [sourcePath, setSourcePath] = useState("");
  const [importing, setImporting] = useState(false);
  const [detailCard, setDetailCard] = useState<Card | null>(null);
  const [greetings, setGreetings] = useState<GreetingInfo[]>([]);
  const [greetingsLoading, setGreetingsLoading] = useState(false);

  const loadCards = () => {
    setLoading(true);
    listCards()
      .then(setCards)
      .catch((error) => message.error(getErrorMessage(error)))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadCards();
  }, []);

  const handleImport = async () => {
    if (!sourcePath.trim()) {
      message.warning("请填写来源路径");
      return;
    }
    setImporting(true);
    try {
      const result = await importCard(sourcePath.trim());
      message.success(`已导入角色卡：${result.card_id}`);
      setImportOpen(false);
      setSourcePath("");
      loadCards();
    } catch (error) {
      message.error(getErrorMessage(error));
    } finally {
      setImporting(false);
    }
  };

  const handleDelete = async (cardId: string) => {
    try {
      await deleteCard(cardId);
      message.success("角色卡已删除");
      if (detailCard?.card_id === cardId) {
        setDetailCard(null);
        setGreetings([]);
      }
      loadCards();
    } catch (error) {
      message.error(getErrorMessage(error));
    }
  };

  const openDetails = async (card: Card) => {
    setDetailCard(card);
    setGreetingsLoading(true);
    try {
      setGreetings(await listGreetings(card.card_id));
    } catch (error) {
      setGreetings([]);
      message.error(getErrorMessage(error));
    } finally {
      setGreetingsLoading(false);
    }
  };

  const columns = [
    {
      title: "角色卡名称",
      dataIndex: "name",
      key: "name",
      render: (name: string) => <Text strong>{name}</Text>,
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      render: (status: string) => (
        <Tag color={status === "ready" ? "green" : "orange"}>
          {status === "ready" ? "就绪" : status}
        </Tag>
      ),
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
      render: (time: string) => new Date(time).toLocaleString("zh-CN"),
    },
    {
      title: "操作",
      key: "actions",
      render: (_: unknown, record: Card) => (
        <Space onClick={(event) => event.stopPropagation()}>
          <Button size="small" onClick={() => openDetails(record)}>
            详情
          </Button>
          <Popconfirm
            title="删除这个角色卡及其会话？"
            okText="删除"
            okButtonProps={{ danger: true }}
            onConfirm={() => handleDelete(record.card_id)}
          >
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 16,
          gap: 12,
        }}
      >
        <Text strong style={{ fontSize: 18 }}>
          角色卡
        </Text>
        <Button type="primary" icon={<ImportOutlined />} onClick={() => setImportOpen(true)}>
          导入角色卡
        </Button>
      </div>

      {loading ? (
        <Spin size="large" style={{ display: "block", margin: "100px auto" }} />
      ) : cards.length ? (
        <Table
          dataSource={cards}
          columns={columns}
          rowKey="card_id"
          pagination={false}
          onRow={(record) => ({
            onClick: () => openDetails(record),
            style: { cursor: "pointer" },
          })}
        />
      ) : (
        <Empty description="暂无角色卡" />
      )}

      <Modal
        title="导入角色卡"
        open={importOpen}
        okText="导入"
        confirmLoading={importing}
        onOk={handleImport}
        onCancel={() => setImportOpen(false)}
      >
        <Text type="secondary">来源路径</Text>
        <Input
          style={{ marginTop: 8 }}
          placeholder="F:\\path\\to\\card.json"
          value={sourcePath}
          onChange={(event) => setSourcePath(event.target.value)}
          onPressEnter={handleImport}
        />
      </Modal>

      <Drawer
        title={detailCard ? detailCard.name : "角色卡详情"}
        open={Boolean(detailCard)}
        width={480}
        onClose={() => {
          setDetailCard(null);
          setGreetings([]);
        }}
      >
        {detailCard && (
          <Space direction="vertical" size={12} style={{ width: "100%" }}>
            <Text type="secondary">ID: {detailCard.card_id}</Text>
            <Text type="secondary">版本：{detailCard.version}</Text>
            <Text type="secondary">世界书条目：{detailCard.worldbook_count}</Text>
            <List
              loading={greetingsLoading}
              header={<Text strong>开场白</Text>}
              dataSource={greetings}
              locale={{ emptyText: "暂无开场白" }}
              renderItem={(greeting) => (
                <List.Item>
                  <List.Item.Meta
                    title={
                      <Space>
                        <span>{greeting.label || greeting.greeting_id}</span>
                        {greeting.is_default && <Tag color="blue">默认</Tag>}
                      </Space>
                    }
                    description={greeting.preview || "（空）"}
                  />
                </List.Item>
              )}
            />
          </Space>
        )}
      </Drawer>
    </div>
  );
}
