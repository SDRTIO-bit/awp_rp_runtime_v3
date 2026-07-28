import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { emptyEditorState } from "../../state/editorEvents";
import { EditorRoom } from "./EditorRoom";

const socketState = emptyEditorState();

vi.mock("../../hooks/useEditorSocket", () => ({
  useEditorSocket: () => ({ state: socketState, status: "connected", send: vi.fn() }),
}));
vi.mock("./MessageComposer", () => ({ MessageComposer: () => <div /> }));
vi.mock("./MessageCard", () => ({ MessageCard: () => <div /> }));
vi.mock("./PipelineTimeline", () => ({ PipelineTimeline: () => <div /> }));
vi.mock("./ToolActivity", () => ({ ToolActivity: () => <div /> }));
vi.mock("./ConversationToolbar", () => ({ ConversationToolbar: () => <div /> }));
vi.mock("./ProjectFilePicker", () => ({ ProjectFilePicker: () => <div /> }));

afterEach(cleanup);

it("renders independent streaming messages by message id", () => {
  socketState.partial = { "stream-1": "第一段", "stream-2": "第二段" };

  render(<MemoryRouter><EditorRoom projectId="p1" room="book" /></MemoryRouter>);

  expect(screen.getAllByLabelText("编辑正在回应")).toHaveLength(2);
  expect(screen.getByText("第一段")).toBeVisible();
  expect(screen.getByText("第二段")).toBeVisible();
});
