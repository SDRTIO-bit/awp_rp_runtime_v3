import { DocumentVersion } from "../../api/workspace";

export function VersionHistory({ versions, onSelect }: {
  versions: DocumentVersion[]; onSelect: (version: DocumentVersion) => void;
}) {
  return <div className="version-history">
    <strong>版本历史</strong>
    {versions.map((version) => <button key={version.revision} onClick={() => onSelect(version)}>
      <span>v{version.revision}</span><small>{version.source} · {new Date(version.created_at).toLocaleString()}</small>
    </button>)}
    {!versions.length && <p>还没有手工保存版本。</p>}
  </div>;
}
