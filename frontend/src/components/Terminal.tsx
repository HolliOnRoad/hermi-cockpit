import { useEffect, useRef } from 'react'
import { type Event } from '../hooks/useWebSocket'

type Props = {
  logs: Event[]
}

function levelColor(level?: string): string {
  switch (level) {
    case 'error':
      return '#ef4444'
    case 'warning':
      return '#fbbf24'
    case 'info':
      return '#60a5fa'
    default:
      return '#22c55e'
  }
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
            <span className="terminal-type" style={{ color: levelColor(log.level) }}>
              [{log.type}]
            </span>
            <span className="terminal-msg">{log.message}</span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
