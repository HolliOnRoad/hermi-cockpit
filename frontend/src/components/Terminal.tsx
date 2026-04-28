import { useEffect, useRef } from 'react'
import { type Event } from '../hooks/useWebSocket'

type Props = {
  logs: Event[]
}

function typeColor(type: string): string {
  switch (type) {
    case 'error':
      return '#ef4444'
    case 'done':
      return '#22c55e'
    case 'agent':
      return '#a78bfa'
    case 'tool':
      return '#f59e0b'
    case 'task':
      return '#3b82f6'
    case 'system':
      return '#64748b'
    case 'log':
    default:
      return '#60a5fa'
  }
}

function typeLabel(type: string): string {
  return type.toUpperCase()
}

export function Terminal({ logs }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  return (
    <div className="terminal">
      <div className="terminal-header">
        <span>Terminal</span>
        <span className="terminal-event-count">{logs.length} events</span>
      </div>
      <div className="terminal-body">
        {logs.length === 0 && (
          <div className="terminal-empty">Waiting for events...</div>
        )}
        {logs.map((log, i) => (
          <div key={i} className="terminal-line">
            <span className="terminal-ts">{log.timestamp}</span>
            <span
              className="terminal-type-badge"
              style={{ background: typeColor(log.type) }}
            >
              {typeLabel(log.type)}
            </span>
            {log.source && log.source !== 'system' && (
              <span className="terminal-source">[{log.source}]</span>
            )}
            <span className="terminal-msg">{log.message}</span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
