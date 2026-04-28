import { type ConnectionStatus } from '../hooks/useWebSocket'

type Props = {
  status: ConnectionStatus
  eventCount: number
}

export function DebugBar({ status, eventCount }: Props) {
  return (
    <div className="debug-bar">
      <span className="debug-item">ws://127.0.0.1:8000/ws</span>
      <span className="debug-sep">|</span>
      <span className="debug-item">{status}</span>
      <span className="debug-sep">|</span>
      <span className="debug-item">{eventCount} events</span>
    </div>
  )
}
