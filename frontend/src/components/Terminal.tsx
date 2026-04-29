import { useEffect, useRef, useState } from 'react'
import { Terminal as TerminalIcon, Wrench, CheckCircle, AlertTriangle, Bot, Filter } from 'lucide-react'
import { type Event, type ConnectionStatus } from '../hooks/useWebSocket'

type Props = {
  logs: Event[]
  status: ConnectionStatus
}

function badgeStyle(type: string): { bg: string; fg: string } {
  switch (type) {
    case 'error':      return { bg: '#7c2d12', fg: '#f97316' }
    case 'done':       return { bg: '#1e3a5f', fg: '#93c5fd' }
    case 'agent':      return { bg: '#1e2a4a', fg: '#a5b4fc' }
    case 'tool':       return { bg: '#172554', fg: '#93c5fd' }
    case 'task':       return { bg: '#172554', fg: '#93c5fd' }
    case 'system':     return { bg: '#1f2937', fg: '#9ca3af' }
    case 'test_event': return { bg: '#1f2937', fg: '#9ca3af' }
    case 'query':      return { bg: '#172554', fg: '#93c5fd' }
    case 'log':
    default:           return { bg: '#1e293b', fg: '#94a3b8' }
  }
}

function lineIcon(type: string): import('lucide-react').LucideIcon | null {
  switch (type) {
    case 'tool':   return Wrench
    case 'done':   return CheckCircle
    case 'error':  return AlertTriangle
    case 'agent':  return Bot
    default:       return null
  }
}

function isHttpLog(log: Event): boolean {
  if (log.type !== 'log') return false
  const msg = typeof log.message === 'string' ? log.message : ''
  return msg.includes('GET /health')
      || msg.includes('POST /v1/')
      || msg.includes('GET /v1/')
      || msg.includes('aiohttp.access')
}

function eventLevel(type: string): 'high' | 'medium' | 'low' {
  switch (type) {
    case 'error': case 'done':   return 'high'
    case 'query': case 'tool':
    case 'agent': case 'task':   return 'medium'
    default:                     return 'low'
  }
}

const statusText: Record<ConnectionStatus, string> = {
  connected: 'Connected',
  connecting: 'Connecting',
  disconnected: 'Disconnected',
}

export function Terminal({ logs, status }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const [showSystemLogs, setShowSystemLogs] = useState(false)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  // Der Reihe nach filtern: HTTP → System-Logs → rendern
  let prevWasQueryInfo = false

  const filteredLogs = logs.filter(log => {
    // 1) HTTP access logs IMMER ausblenden (nur bei Toggle sichtbar)
    if (isHttpLog(log) && !showSystemLogs) return false

    return true
  })

  return (
    <div className="terminal">
      <div className="terminal-header">
        <span className="terminal-header-title">
          <TerminalIcon size={14} />
          Live Terminal
        </span>
        <span className="terminal-header-right">
          <label className="system-log-toggle" title="Zeige HTTP/System-Logs">
            <Filter size={12} />
            <span>System</span>
            <input
              type="checkbox"
              checked={showSystemLogs}
              onChange={e => setShowSystemLogs(e.target.checked)}
            />
          </label>
          <span className="terminal-event-count">{filteredLogs.length} events</span>
        </span>
      </div>
      <div className="terminal-body">
        {filteredLogs.length === 0 && (
          <div className="terminal-empty">
            <span className="terminal-empty-icon">&gt;_</span>
            <span className="terminal-empty-text">Hermi ist bereit</span>
            <span className="terminal-empty-sub">Warte auf Eingabe oder starte einen Task</span>
            <div className="terminal-suggestions">
              <span className="terminal-suggestion">Tippe: recherchieren KI News</span>
              <span className="terminal-suggestion">Tippe: analyse code</span>
              <span className="terminal-suggestion">Tippe: plane Projekt</span>
            </div>
            <div className="terminal-cursor">
              <span className="terminal-cursor-label">Listening</span>
              <span className="terminal-cursor-blink">_</span>
            </div>
          </div>
        )}
        {filteredLogs.map((log, i) => {
          const b = badgeStyle(log.type)
          const Icon = lineIcon(log.type)
          const isNew = i < 2
          const lvl = eventLevel(log.type)
          const isQueryInfo = log.type === 'query' && log.level === 'info'

          // Query-Trenner einfuegen
          let separator = null
          if (isQueryInfo && !prevWasQueryInfo) {
            separator = <div key={`sep-${i}`} className="query-separator">Neue Anfrage</div>
          }
          prevWasQueryInfo = isQueryInfo

          return (
            <div key={i}>
              {separator}
              <div
                className={`terminal-line terminal-line--${log.type}${isNew ? ' terminal-line--new' : ''}`}
                data-level={lvl}
                data-type={log.type}
              >
                <span className="terminal-ts">{log.timestamp}</span>
                {Icon && <Icon size={13} className="terminal-line-icon" />}
                <span className="terminal-badge" style={{ background: b.bg, color: b.fg }}>
                  {log.type}
                </span>
                {log.source && <span className="terminal-source">{log.source}</span>}
                <span className="terminal-msg">{log.message}</span>
              </div>
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
