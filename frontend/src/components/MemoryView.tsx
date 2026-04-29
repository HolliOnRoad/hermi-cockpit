import { useEffect, useState, useCallback } from 'react'

export function MemoryView() {
  const [content, setContent] = useState<string | null>(null)

  const fetchMemory = useCallback(() => {
    fetch('http://127.0.0.1:8000/api/memory')
      .then((r) => r.json())
      .then((data) => setContent(data.content ?? ''))
      .catch(() => setContent(''))
  }, [])

  useEffect(() => {
    fetchMemory()
  }, [fetchMemory])

  return (
    <div className="view-panel">
      <div className="view-panel-header">
        <span className="view-panel-title">Memory — Learnings</span>
        <button className="topbar-btn" onClick={fetchMemory}>
          Refresh
        </button>
      </div>
      <div className="view-panel-body">
        {content === null ? (
          <div className="view-empty">Lade...</div>
        ) : content === '' ? (
          <div className="view-empty">Keine Learnings vorhanden</div>
        ) : (
          <pre className="memory-content">{content}</pre>
        )}
      </div>
    </div>
  )
}
