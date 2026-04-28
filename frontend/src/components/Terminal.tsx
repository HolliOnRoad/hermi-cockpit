import { useEffect, useRef } from 'react'
import { type Event } from '../hooks/useWebSocket'

type Props = {
  logs: Event[]
}

function badgeStyle(type: string): { bg: string; fg: string } {
  switch (type) {
    case 'error':
      return { bg: '#7f1d1d', fg: '#fca5a5' }
    case 'done':
      return { bg: '#14532d', fg: '#86efac' }
    case 'agent':
      return { bg: '#3b0764', fg: '#d8b4fe' }
    case 'tool':
      return { bg: '#451a03', fg: '#fcd34d' }
    case 'task':
      return { bg: '#172554', fg: '#93c5fd' }
    case 'system':
      return { bg: '#1f2937', fg: '#9ca3af' }
    case 'test_event':
      return { bg: '#1f2937', fg: '#9ca3af' }
    case 'log':
    default:
      return { bg: '#1e293b', fg: '#94a3b8' }
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
        <span>Live Terminal</span>
        <span className="terminal-event-count">{logs.length} events</span>
      </div>
      <div className="terminal-body">
        {logs.length === 0 && (
          <div className="terminal-empty">
            Waiting for events from Hermi...
          </div>
        )}
        {logs.map((log, i) => {
          const b = badgeStyle(log.type)
          return (
            <div key={i} className="terminal-line">
              <span className="terminal-ts">{log.timestamp}</span>
              <span
                className="terminal-badge"
                style={{ background: b.bg, color: b.fg }}
              >
                {log.type}
              </span>
              {log.source && (
                <span className="terminal-source">{log.source}</span>
              )}
              <span className="terminal-msg">{log.message}</span>
            </div>
          )
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
