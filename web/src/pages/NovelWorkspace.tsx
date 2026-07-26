import { useNavigate, useParams } from "react-router-dom";
import { ProjectTree } from "../components/workspace/ProjectTree";
import { RoomSwitcher } from "../components/workspace/RoomSwitcher";
import { DocumentPane } from "../components/workspace/DocumentPane";
import { EditorRoom } from "../components/workspace/EditorRoom";
import "./NovelWorkspace.css";

export default function NovelWorkspace() {
  const { id = "", room = "book" } = useParams();
  const navigate = useNavigate();
  const selectedRoom = decodeURIComponent(room);
  const goRoom = (next: string) => navigate(`/novels/${encodeURIComponent(id)}/workspace/${encodeURIComponent(next)}`);
  return (
    <div className="workspace-shell">
      <ProjectTree projectId={id} room={selectedRoom} onRoom={goRoom} onPrompt={() => navigate(`/novels/${encodeURIComponent(id)}/prompts`)} />
      <section className="conversation-column">
        <div className="conversation-toolbar">
          <RoomSwitcher room={selectedRoom} onChange={goRoom} />
          <span className="room-context">{selectedRoom === "book" ? "围绕整部作品讨论，不替你决定剧情" : `${selectedRoom.replace("chapter:", "第 ")} 章 · 独立上下文`}</span>
        </div>
        <EditorRoom projectId={id} room={selectedRoom} />
      </section>
      <DocumentPane projectId={id} room={selectedRoom} />
    </div>
  );
}
