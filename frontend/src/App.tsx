import { useEffect, useState } from 'react'

type Event = {
  type: string
  level?: string
  message: string
  timestamp: string
}

function App() {
  const [logs, setLogs] = useState<Event[]>([])

  useEffect(() => {
    const ws = new WebSocket("ws://127.0.0.1:8000/ws")

    ws.onopen = () => {
      console.log("🔌 Verbunden mit Backend")
    }

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      setLogs((prev) => [data, ...prev])
    }

    ws.onerror = (err) => {
      console.error("WebSocket Fehler:", err)
    }

    ws.onclose = () => {
      console.log("❌ Verbindung geschlossen")
    }

    return () => {
      ws.close()
    }
  }, [])

  return (
    <div style={{ background: "#0f172a", color: "#e2e8f0", height: "100vh", padding: "20px", fontFamily: "monospace" }}>
      <h1>🧠 Hermi Cockpit</h1>

      <div style={{ marginTop: "20px" }}>
        <button
          onClick={() => fetch("http://127.0.0.1:8000/test-event")}
          style={{
            padding: "10px",
            background: "#22c55e",
            border: "none",
            cursor: "pointer",
            color: "black"
          }}
        >
          Test Event senden
        </button>
      </div>

      <div style={{ marginTop: "20px" }}>
        <h2>📡 Live Logs</h2>

        <div style={{
          background: "#020617",
          padding: "10px",
          height: "400px",
          overflowY: "auto",
          border: "1px solid #334155"
        }}>
          {logs.map((log, index) => (
            <div key={index} style={{ marginBottom: "8px" }}>
              <span style={{ color: "#64748b" }}>{log.timestamp}</span>{" "}
              <span style={{ color: "#22c55e" }}>[{log.type}]</span>{" "}
              {log.message}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default App
