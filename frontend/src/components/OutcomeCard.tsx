import { useMemo, useRef } from 'react'
import { CheckCircle, Hash, ArrowRightLeft } from 'lucide-react'
import type { Event } from '../hooks/useWebSocket'

type Props = {
  logs: Event[]
}

export function OutcomeCard({ logs }: Props) {
  const cardRef = useRef<HTMLDivElement>(null)

  const { lastResult, lastQuery } = useMemo(() => {
    const result = [...logs].reverse().find(l => l.type === 'done' && l.message) ?? null
    let query: Event | null = null
    if (result) {
      const doneIdx = logs.indexOf(result)
      if (doneIdx !== -1) {
        for (let i = doneIdx + 1; i < logs.length; i++) {
          if (logs[i].type === 'query' && logs[i].level === 'info') {
            query = logs[i]
            break
          }
        }
      }
    }
    return { lastResult: result, lastQuery: query }
  }, [logs])

  if (!lastResult) return null

  const maxLines = 8
  const lines = lastResult.message.split('\n')
  const truncated = lines.length > maxLines
  const displayLines = lines.slice(0, maxLines)

  const tokens = lastResult.meta as Record<string, unknown> | undefined
  const inputTokens = tokens?.input_tokens != null ? String(tokens.input_tokens) : null
  const outputTokens = tokens?.output_tokens != null ? String(tokens.output_tokens) : null

  return (
    <div className="outcome-card" ref={cardRef}>
      <div className="outcome-card-header">
        <CheckCircle size={16} className="outcome-card-icon" />
        <span className="outcome-card-title">Ergebnis</span>
        {(inputTokens || outputTokens) && (
          <span className="outcome-card-meta">
            {inputTokens && (
              <span className="outcome-card-token">
                <ArrowRightLeft size={11} />
                in: {inputTokens}
              </span>
            )}
            {outputTokens && (
              <span className="outcome-card-token">
                <Hash size={11} />
                out: {outputTokens}
              </span>
            )}
          </span>
        )}
      </div>
      {lastQuery && (
        <div className="outcome-card-query">{lastQuery.message}</div>
      )}
      <div className="outcome-card-body">
        {displayLines.map((line, i) => (
          <div key={i} className="outcome-card-line">{line}</div>
        ))}
        {truncated && (
          <div className="outcome-card-more">… {lines.length - maxLines} weitere Zeilen</div>
        )}
      </div>
    </div>
  )
}
