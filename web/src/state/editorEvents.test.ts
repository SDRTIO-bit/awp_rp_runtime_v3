import { expect, it } from "vitest";
import { applyEditorEvent, emptyEditorState } from "./editorEvents";

it("deduplicates replay and replaces deltas with the completed message", () => {
  let state = emptyEditorState();
  for (const event of [
    { event_id: 1, type: "editor_delta", payload: { message_id: "m1", text: "先" } },
    { event_id: 2, type: "editor_delta", payload: { message_id: "m1", text: "确定" } },
    { event_id: 2, type: "editor_delta", payload: { message_id: "m1", text: "确定" } },
    { event_id: 3, type: "editor_message_completed", payload: { message_id: "m1", text: "先确定" } },
  ]) state = applyEditorEvent(state, event);
  expect(state.messages).toEqual([{ id: "m1", role: "editor", text: "先确定" }]);
  expect(state.lastEventId).toBe(3);
  expect(state.partial).toEqual({});
});
