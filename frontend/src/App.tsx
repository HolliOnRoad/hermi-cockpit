import { useWebSocket } from './hooks/useWebSocket'
import { TopBar } from './components/TopBar'
import { Terminal } from './components/Terminal'
import { Sidebar } from './components/Sidebar'
import { DebugBar } from './components/DebugBar'

function App() {
  const { status, logs, sendTestEvent } = useWebSocket()

  return (
    <div className="app">
      <TopBar status={status} />

      <main className="main">
        <section className="terminal-section">
          <Terminal logs={logs} />
        </section>
        <Sidebar />
      </main>

      <div className="test-bar">
        <button className="test-btn" onClick={sendTestEvent}>
          Test Event senden
        </button>
      </div>

      <DebugBar status={status} eventCount={logs.length} />
    </div>
  )
}

export default App
