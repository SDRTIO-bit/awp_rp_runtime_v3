import { useEffect, useState } from "react";

export function MessageComposer({ storageKey, disabled, onSend, onCancel }: {
  storageKey: string; disabled: boolean; onSend: (text: string) => void; onCancel: () => void;
}) {
  const [text, setText] = useState(() => sessionStorage.getItem(storageKey) ?? "");
  useEffect(() => { sessionStorage.setItem(storageKey, text); }, [storageKey, text]);
  const submit = () => {
    const value = text.trim(); if (!value) return;
    onSend(value); setText(""); sessionStorage.removeItem(storageKey);
  };
  return <div className="message-composer">
    <textarea value={text} maxLength={20000} onChange={(e) => setText(e.target.value)}
      onKeyDown={(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) submit(); }}
      placeholder="把你的剧情安排、犹豫和不确定都告诉编辑。Ctrl + Enter 发送。" />
    <div><span>{text.length.toLocaleString()} / 20,000</span>
      <button className="quiet-button" onClick={onCancel}>停止</button>
      <button className="primary-button" disabled={disabled || !text.trim()} onClick={submit}>发送给编辑</button>
    </div>
  </div>;
}
