import { useEffect, useState, useCallback, useMemo } from 'react'
import { Bot } from 'lucide-react'
import type { Event } from '../hooks/useWebSocket'

type Agent = {
  name: string
  runs: number
  last_run: string | null
  errors: number
  reifegrad: string
}

type Props = {
  logs: Event[]
}

export function AgentsView({ logs }: Props) {
  const [agents, setAgents] = useState<Agent[]>([])
  const [startedAgent, setStartedAgent] = useState<string | null>(null)

  const fetchAgents = useCallback(() => {
    fetch('http://127.0.0.1:8000/api/agents')
      .then((r) => r.json())
      .then((data) => setAgents(data.agents ?? []))
      .catch(() => setAgents([]))
  }, [])

  useEffect(() => {
    fetchAgents()
  }, [fetchAgents])

  const queryRunning = useMemo(() => {
    if (!startedAgent) return false
    for (let i = 0; i < logs.length; i++) {
      const log = logs[i]
      if (
        (log.type === 'query' && log.level === 'success') ||
        (log.type === 'error' && log.message?.includes('Query fehlgeschlagen'))
      ) {
        return false
      }
    }
    return true
  }, [logs, startedAgent])

  const startAgent = useCallback(async (name: string) => {
    if (queryRunning) return
    setStartedAgent(name)
    try {
      await fetch('http://127.0.0.1:8000/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: '/' + name }),
      })
    } catch {
      setStartedAgent(null)
    }
  }, [queryRunning])

  if (agents.length === 0) {
    return (
      <div className="view-panel">
        <div className="view-panel-header">
          <span className="view-panel-title">
            <Bot size={14} className="view-panel-icon" />
            Agenten
          </span>
        </div>
        <div className="view-panel-body">
          <div className="view-empty">Keine Agenten gefunden</div>
        </div>
      </div>
    )
  }

  return (
    <div className="view-panel">
      <div className="view-panel-header">
        <span className="view-panel-title">
          <Bot size={14} className="view-panel-icon" />
          Agenten
        </span>
        <span className="view-panel-sub">
          {queryRunning ? 'Query laeuft...' : `${agents.length} Skills`}
        </span>
      </div>
      <div className="view-panel-body">
        <div className="agents-grid">
          {agents.map((a) => (
            <div key={a.name} className="agent-card">
              <div className="agent-card-header">
                <span className="agent-card-name">{a.name}</span>
                {a.errors > 0 && (
                  <span className="agent-error-badge">{a.errors}</span>
                )}
              </div>
              <div className="agent-card-meta">
                <span>
                  Runs: <strong>{a.runs}</strong>
                </span>
                <span>
                  Letzte:{' '}
                  {a.last_run ?? 'Noch nie'}
                </span>
              </div>
              <button
                className="agent-start-btn"
                onClick={() => startAgent(a.name)}
                disabled={queryRunning}
              >
                Start
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
