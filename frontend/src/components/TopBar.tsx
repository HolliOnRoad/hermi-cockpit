import { type ConnectionStatus } from '../hooks/useWebSocket'

type Props = {
  status: ConnectionStatus
  eventCount: number
  onTestEvent: () => void
}

const statusLabel: Record<ConnectionStatus, string> = {
  connecting: 'connecting',
  connected: 'online',
  disconnected: 'offline',
}

export function TopBar({ status, eventCount, onTestEvent }: Props) {
  return (
    <header className="topbar">
      <div className="topbar-left">
        <span className="topbar-brand">Hermi Cockpit</span>
        <span className="topbar-status">
          <span className={`status-pill status-${status}`}>
            {statusLabel[status]}
          </span>
        </span>
      </div>

      <div className="topbar-center">
        <span className="topbar-metric">
          <span className="topbar-key">Events</span>
          <span className="topbar-value">{eventCount}</span>
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

      <div className="topbar-right">
        <button className="topbar-btn" onClick={onTestEvent}>
          Test Event
        </button>
      </div>
    </header>
  )
}
