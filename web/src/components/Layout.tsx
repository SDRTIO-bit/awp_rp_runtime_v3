import { Outlet, useNavigate, useLocation } from "react-router-dom";
import { Layout, Menu } from "antd";
import { MessageOutlined, AppstoreOutlined } from "@ant-design/icons";

const { Sider, Content } = Layout;

export default function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();

  const selectedKey = location.pathname.startsWith("/cards") ? "/cards" : "/sessions";

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider width={200} theme="light">
        <div style={{ padding: "16px", fontWeight: "bold", fontSize: 16, textAlign: "center" }}>
          AWP RP
        </div>
        <Menu
          mode="inline"
          selectedKeys={[selectedKey]}
          items={[
            { key: "/sessions", icon: <MessageOutlined />, label: "会话" },
            { key: "/cards", icon: <AppstoreOutlined />, label: "角色卡" },
          ]}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Content style={{ padding: 24, background: "#f5f5f5", overflow: "auto" }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
