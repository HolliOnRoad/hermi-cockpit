import { useWebSocket } from './hooks/useWebSocket'
import { TopBar } from './components/TopBar'
import { Terminal } from './components/Terminal'
import { Sidebar } from './components/Sidebar'
import { DebugBar } from './components/DebugBar'
import { QueryInput } from './components/QueryInput'

function App() {
  const { status, logs, sendTestEvent } = useWebSocket()

  return (
    <div className="cockpit-container">
      <TopBar
        status={status}
        eventCount={logs.length}
        onTestEvent={sendTestEvent}
      />

      <main className="main">
        <section className="terminal-section">
          <Terminal logs={logs} status={status} />
          <QueryInput logs={logs} />
        </section>
        <Sidebar logs={logs} />
      </main>

      <DebugBar status={status} eventCount={logs.length} />
    </div>
  )
}

export default App
