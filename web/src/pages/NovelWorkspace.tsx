import { useState, useMemo } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ProjectTree } from "../components/workspace/ProjectTree";
import { RoomSwitcher } from "../components/workspace/RoomSwitcher";
import { DocumentPane } from "../components/workspace/DocumentPane";
import { EditorRoom } from "../components/workspace/EditorRoom";
import { ChangesPane } from "../components/workspace/ChangesPane";
import { useEditorSocket } from "../hooks/useEditorSocket";
import "./NovelWorkspace.css";

export default function NovelWorkspace() {
  const { id = "", room = "book" } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const [leftOpen, setLeftOpen] = useState(false);
  const [rightOpen, setRightOpen] = useState(false);
  const [rightTab, setRightTab] = useState<"documents" | "changes">("documents");

  const selectedRoom = decodeURIComponent(room);
  const branchId = searchParams.get("conversation") || "main";
  const goRoom = (next: string) =>
    navigate(`/novels/${encodeURIComponent(id)}/workspace/${encodeURIComponent(next)}`);

  const handleBranchChange = (newBranchId: string) => {
    setSearchParams({ conversation: newBranchId });
  };

  return (
    <div className="workspace-shell">
      <ProjectTree
        open={leftOpen}
        onClose={() => setLeftOpen(false)}
        projectId={id}
        room={selectedRoom}
        onRoom={(next) => { setLeftOpen(false); goRoom(next); }}
        onPrompt={() => navigate(`/novels/${encodeURIComponent(id)}/prompts`)}
      />
      <section className="conversation-column">
        <div className="conversation-toolbar">
          <button
            className="mobile-pane-button"
            onClick={() => { setRightOpen(false); setLeftOpen((v) => !v); }}
          >
            项目
          </button>
          <RoomSwitcher room={selectedRoom} onChange={goRoom} />
          <span className="room-context">
            {selectedRoom === "book"
              ? "围绕整部作品讨论，不替你决定剧情"
              : `${selectedRoom.replace("chapter:", "第 ")} 章 · 独立上下文`}
          </span>
          <button
            className="mobile-pane-button"
            onClick={() => { setLeftOpen(false); setRightOpen((v) => !v); }}
          >
            文档
          </button>
        </div>
        <EditorRoom
          projectId={id}
          room={selectedRoom}
          branchId={branchId}
          onBranchChange={handleBranchChange}
        />
      </section>

      {/* Right pane with tab switching */}
      {rightTab === "documents" ? (
        <DocumentPane
          open={rightOpen}
          onClose={() => setRightOpen(false)}
          projectId={id}
          room={selectedRoom}
          extraTabs={
            <button
              className="tab-switch-btn"
              onClick={() => setRightTab("changes")}
            >
              任务与改动
            </button>
          }
        />
      ) : (
        <div className={`document-pane ${rightOpen ? "open" : ""}`}>
          <div className="pane-toolbar">
            <button onClick={() => setRightTab("documents")}>← 文档</button>
            <button className="mobile-pane-button" onClick={() => setRightOpen(false)}>收起</button>
          </div>
          <ChangesPane
            turns={{
              "main": { id: "main", status: "completed", messageIds: [], activity: [], changes: [], pipeline: [] }
            }}
            turnIds={["main"]}
          />
        </div>
      )}
    </div>
  );
}
