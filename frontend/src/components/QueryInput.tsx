import { useState, useRef, useCallback, useMemo, type KeyboardEvent } from 'react'
import type { Event } from '../hooks/useWebSocket'

type Props = {
  logs: Event[]
}

export function QueryInput({ logs }: Props) {
  const [text, setText] = useState('')
  const [submissionId, setSubmissionId] = useState(0)
  const [errorState, setErrorState] = useState<string | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const queryRunning = useMemo(() => {
    if (submissionId === 0) return false
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
  }, [logs, submissionId])

  const sendQuery = useCallback(async () => {
    const trimmed = text.trim()
    if (!trimmed || queryRunning || errorState !== null) return

    try {
      const res = await fetch('http://127.0.0.1:8000/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: trimmed }),
      })

      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        const msg = data.detail || data.error || `Error ${res.status}`
        setErrorState(msg)
        setTimeout(() => setErrorState(null), 3000)
      } else {
        setSubmissionId((id) => id + 1)
        setText('')
      }
    } catch {
      setErrorState('Verbindungsfehler')
      setTimeout(() => setErrorState(null), 3000)
    }
  }, [text, queryRunning, errorState])

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendQuery()
    }
  }

  const isDisabled = queryRunning || errorState !== null
  const placeholder = errorState
    ? errorState
    : queryRunning
      ? 'Hermes läuft...'
      : 'Auftrag eingeben...'

  return (
    <div className="query-input-container">
      <textarea
        ref={textareaRef}
        className={`query-input${isDisabled ? ' query-input--disabled' : ''}`}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={isDisabled}
        rows={2}
      />
      <button
        className="query-send-btn"
        onClick={sendQuery}
        disabled={isDisabled}
      >
        Send
      </button>
    </div>
  )
}
