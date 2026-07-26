export function RoomSwitcher({
  room, onChange,
}: { room: string; onChange: (room: string) => void }) {
  return (
    <div className="room-switcher" role="tablist" aria-label="编辑房间">
      <button className={room === "book" ? "active" : ""} onClick={() => onChange("book")}>全书编辑室</button>
      <button className={room !== "book" ? "active" : ""} onClick={() => room !== "book" && onChange(room)}>章节编辑室</button>
    </div>
  );
}
