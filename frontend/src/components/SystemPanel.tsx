const metrics = [
  { label: 'CPU', value: '--' },
  { label: 'RAM', value: '--' },
  { label: 'Disk', value: '--' },
]

export function SystemPanel() {
  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">System</span>
        <span className="pill pill-idle">Demo</span>
      </div>
      <div className="panel-body">
        <div className="system-list">
          {metrics.map((m) => (
            <div key={m.label} className="system-row">
              <span className="system-key">{m.label}</span>
              <span className="system-value">{m.value}</span>
            </div>
          ))}
        </div>
        <div className="panel-note">
          No live system data available
        </div>
      </div>
    </div>
  )
}
