type ToolDef = {
  label: string
  icon: string
  available: boolean
}

const tools: ToolDef[] = [
  { label: 'Terminal', icon: '>_', available: true },
  { label: 'Web Search', icon: '~', available: false },
  { label: 'Obsidian', icon: 'O', available: false },
  { label: 'Skills', icon: 'S', available: false },
  { label: 'Files', icon: 'F', available: false },
  { label: 'Browser', icon: 'B', available: false },
]

export function ToolsPanel() {
  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Tools</span>
      </div>
      <div className="panel-body">
        <div className="tools-grid">
          {tools.map((t) => (
            <span
              key={t.label}
              className={`tool-chip ${t.available ? '' : 'tool-disabled'}`}
              title={t.available ? t.label : `${t.label} (later)`}
            >
              <span className="tool-icon">{t.icon}</span>
              <span className="tool-label">{t.label}</span>
              {!t.available && <span className="tool-tag">soon</span>}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}
