import { useEffect, useRef } from 'react'
import { Terminal as TerminalIcon, Wrench, CheckCircle, AlertTriangle, Bot } from 'lucide-react'
import { type Event, type ConnectionStatus } from '../hooks/useWebSocket'

type Props = {
  logs: Event[]
  status: ConnectionStatus
}

function badgeStyle(type: string): { bg: string; fg: string } {
  switch (type) {
    case 'error':
      return { bg: '#7c2d12', fg: '#f97316' }
    case 'done':
      return { bg: '#1e3a5f', fg: '#93c5fd' }
    case 'agent':
      return { bg: '#1e2a4a', fg: '#a5b4fc' }
    case 'tool':
      return { bg: '#172554', fg: '#93c5fd' }
    case 'task':
      return { bg: '#172554', fg: '#93c5fd' }
    case 'system':
      return { bg: '#1f2937', fg: '#9ca3af' }
    case 'test_event':
      return { bg: '#1f2937', fg: '#9ca3af' }
    case 'query':
      return { bg: '#172554', fg: '#93c5fd' }
    case 'log':
    default:
      return { bg: '#1e293b', fg: '#94a3b8' }
  }
}

function lineIcon(type: string): import('lucide-react').LucideIcon | null {
  switch (type) {
    case 'tool':
      return Wrench
    case 'done':
      return CheckCircle
    case 'error':
      return AlertTriangle
    case 'agent':
      return Bot
    default:
      return null
  }
}

const statusText: Record<ConnectionStatus, string> = {
  connected: 'Connected',
  connecting: 'Connecting',
  disconnected: 'Disconnected',
}

export function Terminal({ logs, status }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  return (
    <div className="terminal">
      <div className="terminal-header">
        <span className="terminal-header-title">
          <TerminalIcon size={14} />
          Live Terminal
        </span>
        <span className="terminal-event-count">{logs.length} events</span>
      </div>
      <div className="terminal-body">
        {logs.length === 0 && (
          <div className="terminal-empty">
            <span className="terminal-empty-icon">&gt;_</span>
            <span className="terminal-empty-text">
              Hermi ist bereit
            </span>
            <span className="terminal-empty-sub">
              Warte auf Eingabe oder starte einen Task
            </span>
            <div className="terminal-suggestions">
              <span className="terminal-suggestion">
                Tippe: recherchieren KI News
              </span>
              <span className="terminal-suggestion">
                Tippe: analyse code
              </span>
              <span className="terminal-suggestion">
                Tippe: plane Projekt
              </span>
            </div>
            <div className="terminal-cursor">
              <span className="terminal-cursor-label">Listening</span>
              <span className="terminal-cursor-blink">_</span>
            </div>
          </div>
        )}
        {logs.map((log, i) => {
          const b = badgeStyle(log.type)
          const Icon = lineIcon(log.type)
          const isNew = i < 2
          return (
            <div
              key={i}
              className={`terminal-line terminal-line--${log.type}${isNew ? ' terminal-line--new' : ''}`}
            >
              <span className="terminal-ts">{log.timestamp}</span>
              {Icon && (
                <Icon size={13} className="terminal-line-icon" />
              )}
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
      <div className="terminal-footer">
        <span className="terminal-footer-item">
          <span>ws://127.0.0.1:8000/ws</span>
        </span>
        <span className="terminal-footer-item">
          <span className={`terminal-footer-status terminal-footer-status--${status}`}>
            {statusText[status]}
          </span>
        </span>
      </div>
    </div>
  )
}
