const dummyAgents = [
  { name: 'Classifier', status: 'active' as const },
  { name: 'Code-Analyzer', status: 'idle' as const },
  { name: 'Planner', status: 'idle' as const },
  { name: 'Executor', status: 'idle' as const },
  { name: 'Reviewer', status: 'error' as const },
]

const statusColor: Record<string, string> = {
  active: '#22c55e',
  idle: '#64748b',
  error: '#ef4444',
}

const dummySystem = {
  cpu: '12%',
  ram: '3.2 GB / 16 GB',
  disk: '42 GB / 250 GB',
}

export function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-block">
        <div className="sidebar-title">Agents</div>
        <div className="agent-list">
          {dummyAgents.map((agent) => (
            <div key={agent.name} className="agent-row">
              <span
                className="agent-dot"
                style={{ background: statusColor[agent.status] }}
              />
              <span className="agent-name">{agent.name}</span>
              <span
                className="agent-status"
                style={{ color: statusColor[agent.status] }}
              >
                {agent.status}
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="sidebar-block">
        <div className="sidebar-title">System</div>
        <div className="system-info">
          <div className="system-row">
            <span className="system-key">CPU</span>
            <span className="system-value">{dummySystem.cpu}</span>
          </div>
          <div className="system-row">
            <span className="system-key">RAM</span>
            <span className="system-value">{dummySystem.ram}</span>
          </div>
          <div className="system-row">
            <span className="system-key">Disk</span>
            <span className="system-value">{dummySystem.disk}</span>
          </div>
        </div>
      </div>
    </aside>
  )
}
