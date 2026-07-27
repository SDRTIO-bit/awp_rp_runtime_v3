import { useState, useCallback, useEffect } from "react";
import { listProjectFiles } from "../../api/workspace";

interface Props {
  projectId: string;
  selected: string[];
  onSelect: (path: string) => void;
  onRemove: (path: string) => void;
  maxReferences?: number;
}

export function ProjectFilePicker({ projectId, selected, onSelect, onRemove, maxReferences = 12 }: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [files, setFiles] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const results = await listProjectFiles(projectId, query);
        setFiles(results.filter((f) => !selected.includes(f)));
      } catch { setFiles([]); }
      setLoading(false);
    }, 200);
    return () => clearTimeout(timer);
  }, [projectId, query, open, selected]);

  const handleToggleFile = (path: string) => {
    if (selected.includes(path)) {
      onRemove(path);
    } else {
      if (selected.length >= maxReferences) return;
      onSelect(path);
    }
  };

  return (
    <div className="project-file-picker">
      <div className="selected-files">
        {selected.map((path) => (
          <span key={path} className="file-chip" title={path}>
            @{path}
            <button onClick={() => onRemove(path)} aria-label={`移除文件 ${path}`}>×</button>
          </span>
        ))}
      </div>
      <button
        className="picker-toggle"
        onClick={() => setOpen(!open)}
        disabled={selected.length >= maxReferences}
        aria-label="添加项目文件引用"
      >
        @文件
      </button>
      {open && (
        <div className="picker-dropdown">
          <input
            className="picker-search"
            placeholder="搜索项目文件..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            autoFocus
            aria-label="搜索项目文件"
          />
          <ul className="picker-list" role="listbox">
            {loading && <li className="picker-loading">搜索中...</li>}
            {!loading && files.length === 0 && <li className="picker-empty">无匹配文件</li>}
            {files.map((path) => (
              <li
                key={path}
                role="option"
                className={`picker-item ${selected.includes(path) ? "selected" : ""}`}
                onClick={() => handleToggleFile(path)}
              >
                {path}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
