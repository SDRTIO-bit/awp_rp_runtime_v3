import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it } from "vitest";
import { ThemeProvider, useWorkspaceTheme } from "./ThemeProvider";

function Probe() {
  const { theme, setTheme } = useWorkspaceTheme();
  return <button data-testid="theme" onClick={() => setTheme("graphite")}>{theme}</button>;
}

it("defaults to paper and persists graphite", async () => {
  localStorage.clear();
  render(<ThemeProvider><Probe /></ThemeProvider>);
  expect(screen.getByTestId("theme")).toHaveTextContent("paper");
  await userEvent.click(screen.getByRole("button"));
  expect(localStorage.getItem("novel-coding-theme")).toBe("graphite");
  expect(document.documentElement.dataset.theme).toBe("graphite");
});
