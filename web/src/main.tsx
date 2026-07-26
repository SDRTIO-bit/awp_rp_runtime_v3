import React, { Suspense, lazy } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import AppLayout from "./components/Layout";
import { ThemeProvider } from "./components/workspace/ThemeProvider";
import "./styles/global.css";

const Novels = lazy(() => import("./pages/Novels"));
const NovelDetail = lazy(() => import("./pages/NovelDetail"));
const NovelWorkspace = lazy(() => import("./pages/NovelWorkspace"));
const PromptStudio = lazy(() => import("./pages/PromptStudio"));

const routeFallback = (
  <div style={{ padding: 24, color: "#666" }}>
    Loading...
  </div>
);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ThemeProvider>
    <ConfigProvider locale={zhCN} theme={{ token: { colorPrimary: "#8b3f35" } }}>
      <BrowserRouter basename="/awp">
        <Suspense fallback={routeFallback}>
          <Routes>
            <Route element={<AppLayout />}>
              <Route path="/" element={<Navigate to="/novels" replace />} />
              <Route path="/novels" element={<Novels />} />
              <Route path="/novels/:id" element={<NovelDetail />} />
              <Route path="/novels/:id/workspace/:room?" element={<NovelWorkspace />} />
              <Route path="/novels/:id/prompts" element={<PromptStudio />} />
              <Route path="*" element={<Navigate to="/novels" replace />} />
            </Route>
          </Routes>
        </Suspense>
      </BrowserRouter>
    </ConfigProvider>
    </ThemeProvider>
  </React.StrictMode>
);
