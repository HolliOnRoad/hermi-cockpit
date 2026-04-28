import { useEffect, useRef, useState, useCallback } from 'react'

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected'

export type Event = {
  type: string
  level?: string
  message: string
  timestamp: string
}

const WS_URL = 'ws://127.0.0.1:8000/ws'
const MAX_LOGS = 500
const RECONNECT_INTERVAL = 3000

export function useWebSocket() {
  const [status, setStatus] = useState<ConnectionStatus>('disconnected')
  const [logs, setLogs] = useState<Event[]>([])
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const connectRef = useRef<() => void>(() => {})

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    setStatus('connecting')
    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => {
      setStatus('connected')
    }

    ws.onmessage = (raw) => {
      try {
        const data = JSON.parse(raw.data)
        setLogs((prev) => {
          const next = [data, ...prev]
          return next.length > MAX_LOGS ? next.slice(0, MAX_LOGS) : next
        })
      } catch {
        // ignore malformed messages
      }
    }

    ws.onerror = (err) => {
      console.warn('WebSocket error:', WS_URL, err)
    }

    ws.onclose = () => {
      setStatus('disconnected')
      wsRef.current = null
      reconnectTimeoutRef.current = setTimeout(() => connectRef.current(), RECONNECT_INTERVAL)
    }
  }, [])

  useEffect(() => {
    connectRef.current = connect
  })

  const sendTestEvent = useCallback(async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/test-event')
      const data = await res.json()
      console.log('Test event response:', data)
    } catch (err) {
      console.warn('Test event failed:', err)
    }
  }, [])

  useEffect(() => {
    connect()
    return () => {
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current)
      wsRef.current?.close()
    }
  }, [connect])

  return { status, logs, sendTestEvent }
}
