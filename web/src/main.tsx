import React, { Suspense, lazy } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import AppLayout from "./components/Layout";

const Novels = lazy(() => import("./pages/Novels"));
const NovelDetail = lazy(() => import("./pages/NovelDetail"));

const routeFallback = (
  <div style={{ padding: 24, color: "#666" }}>
    Loading...
  </div>
);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ConfigProvider locale={zhCN} theme={{ token: { colorPrimary: "#1677ff" } }}>
      <BrowserRouter basename="/awp">
        <Suspense fallback={routeFallback}>
          <Routes>
            <Route element={<AppLayout />}>
              <Route path="/" element={<Navigate to="/novels" replace />} />
              <Route path="/novels" element={<Novels />} />
              <Route path="/novels/:id" element={<NovelDetail />} />
              <Route path="*" element={<Navigate to="/novels" replace />} />
            </Route>
          </Routes>
        </Suspense>
      </BrowserRouter>
    </ConfigProvider>
  </React.StrictMode>
);
