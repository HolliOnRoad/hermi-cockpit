import { useEffect, useState } from 'react'
import { type ConnectionStatus } from '../hooks/useWebSocket'

type Props = {
  status: ConnectionStatus
  eventCount: number
  onTestEvent: () => void
}

type GatewayStatus = {
  gateway_state: string
  active_agents_count: number
  updated_at: string
}

const statusLabel: Record<ConnectionStatus, string> = {
  connecting: 'connecting',
  connected: 'online',
  disconnected: 'offline',
}

export function TopBar({ status, eventCount, onTestEvent }: Props) {
  const [gateway, setGateway] = useState<GatewayStatus | null>(null)

  useEffect(() => {
    const fetchStatus = () => {
      fetch('http://127.0.0.1:8000/api/status')
        .then((r) => r.json())
        .then((data) => {
          if (!data.error) setGateway(data)
        })
        .catch(() => {})
    }

    fetchStatus()
    const interval = setInterval(fetchStatus, 5000)
    return () => clearInterval(interval)
  }, [])

  return (
    <header className="topbar">
      <div className="topbar-left">
        <span className="topbar-brand">Hermi Cockpit</span>
        <span className="topbar-status">
          <span className={`status-pill status-${status}`}>
            {statusLabel[status]}
          </span>
        </span>
        {gateway && (
          <span className="topbar-status">
            <span className={`status-pill ${gateway.gateway_state === 'running' ? 'status-connecting' : gateway.gateway_state === 'active' ? 'status-connected' : 'status-disconnected'}`}>
              {gateway.gateway_state}
            </span>
          </span>
        )}
      </div>

      <div className="topbar-center">
        <span className="topbar-metric">
          <span className="topbar-key">Events</span>
          <span className="topbar-value">{eventCount}</span>
        </span>
        <span className="topbar-metric">
          <span className="topbar-key">Gateway</span>
          <span className="topbar-value">{gateway?.gateway_state ?? '--'}</span>
        </span>
        {gateway && gateway.active_agents_count > 0 && (
          <span className="topbar-metric">
            <span className="topbar-key">Agents</span>
            <span className="topbar-value">{gateway.active_agents_count}</span>
          </span>
        )}
      </div>

      <div className="topbar-right">
        <button className="topbar-btn" onClick={onTestEvent}>
          Test Event
        </button>
      </div>
    </header>
  )
}
