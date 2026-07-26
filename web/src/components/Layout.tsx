import { Outlet, useNavigate } from "react-router-dom";
import { useWorkspaceTheme, WorkspaceTheme } from "./workspace/ThemeProvider";

const labels: Record<WorkspaceTheme, string> = {
  paper: "墨与纸",
  graphite: "石墨",
  studio: "纯净白",
};

export default function AppLayout() {
  const navigate = useNavigate();
  const { theme, setTheme } = useWorkspaceTheme();
  return (
    <div className="app-frame">
      <header className="app-header">
        <button className="brand" onClick={() => navigate("/novels")}>
          <span className="brand-mark">文</span>
          <span><strong>Novel Coding</strong><small>专属写作工作区</small></span>
        </button>
        <div className="theme-switcher" aria-label="主题">
          {(Object.keys(labels) as WorkspaceTheme[]).map((item) => (
            <button
              key={item}
              className={theme === item ? "active" : ""}
              onClick={() => setTheme(item)}
            >{labels[item]}</button>
          ))}
        </div>
      </header>
      <div className="app-content"><Outlet /></div>
    </div>
  );
}
