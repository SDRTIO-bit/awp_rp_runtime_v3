import { createContext, useContext, useEffect, useMemo, useState } from "react";

export type WorkspaceTheme = "paper" | "graphite" | "studio";
const themes: WorkspaceTheme[] = ["paper", "graphite", "studio"];
const ThemeContext = createContext<{
  theme: WorkspaceTheme;
  setTheme: (theme: WorkspaceTheme) => void;
}>({ theme: "paper", setTheme: () => undefined });

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<WorkspaceTheme>(() => {
    const stored = localStorage.getItem("novel-coding-theme") as WorkspaceTheme | null;
    return stored && themes.includes(stored) ? stored : "paper";
  });
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("novel-coding-theme", theme);
  }, [theme]);
  const value = useMemo(() => ({ theme, setTheme }), [theme]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export const useWorkspaceTheme = () => useContext(ThemeContext);
