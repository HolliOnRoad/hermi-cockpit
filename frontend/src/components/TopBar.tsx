import { type ConnectionStatus } from '../hooks/useWebSocket'

type Props = {
  status: ConnectionStatus
}

const statusLabel: Record<ConnectionStatus, string> = {
  connecting: 'connecting',
  connected: 'online',
  disconnected: 'offline',
}

const statusColor: Record<ConnectionStatus, string> = {
  connecting: '#fbbf24',
  connected: '#22c55e',
  disconnected: '#ef4444',
}

export function TopBar({ status }: Props) {
  return (
    <header className="topbar">
      <div className="topbar-section">
        <span className="status-dot" style={{ background: statusColor[status] }} />
        <span className="status-label">Backend: {statusLabel[status]}</span>
      </div>

      <div className="topbar-section">
        <span className="topbar-metric">
          <span className="topbar-key">Task</span>
          <span className="topbar-value">idle</span>
        </span>
        <span className="topbar-metric">
          <span className="topbar-key">Model</span>
          <span className="topbar-value">hermi-v1</span>
        </span>
        <span className="topbar-metric">
          <span className="topbar-key">Cost</span>
          <span className="topbar-value">$0.00</span>
        </span>
      </div>
    </header>
  )
}
