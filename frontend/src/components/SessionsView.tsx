import { useEffect, useState, useCallback } from 'react'

type Session = {
  id: number
  source: string
  model: string
  title: string | null
  started_at: string
  ended_at: string | null
  input_tokens: number
  output_tokens: number
  estimated_cost_usd: number | null
}

function fmtTokens(input: number, output: number): string {
  const total = input + output
  if (total >= 1000) {
    return (total / 1000).toFixed(1) + 'k'
  }
  return String(total)
}

export function SessionsView() {
  const [sessions, setSessions] = useState<Session[]>([])

  const fetchSessions = useCallback(() => {
    fetch('http://127.0.0.1:8000/api/sessions')
      .then((r) => r.json())
      .then((data) => setSessions(data.sessions ?? []))
      .catch(() => setSessions([]))
  }, [])

  useEffect(() => {
    fetchSessions()
  }, [fetchSessions])

  return (
    <div className="view-panel">
      <div className="view-panel-header">
        <span className="view-panel-title">Sessions</span>
      </div>
      <div className="view-panel-body">
        {sessions.length === 0 ? (
          <div className="view-empty">Keine Sessions gefunden</div>
        ) : (
          <table className="sessions-table">
            <thead>
              <tr>
                <th>Titel</th>
                <th>Model</th>
                <th>Tokens</th>
                <th>Gestartet</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((s) => (
                <tr key={s.id}>
                  <td>{s.title || '\u2014'}</td>
                  <td>{s.model}</td>
                  <td>{fmtTokens(s.input_tokens, s.output_tokens)}</td>
                  <td>{s.started_at || '\u2014'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
