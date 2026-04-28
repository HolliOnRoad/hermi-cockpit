import { useWebSocket } from './hooks/useWebSocket'
import { TopBar } from './components/TopBar'
import { Terminal } from './components/Terminal'
import { Sidebar } from './components/Sidebar'
import { DebugBar } from './components/DebugBar'

function App() {
  const { status, logs, sendTestEvent } = useWebSocket()

  return (
    <div className="app">
      <TopBar
        status={status}
        eventCount={logs.length}
        onTestEvent={sendTestEvent}
      />

      <main className="main">
        <section className="terminal-section">
          <Terminal logs={logs} />
        </section>
        <Sidebar logs={logs} />
      </main>

      <DebugBar status={status} eventCount={logs.length} />
    </div>
  )
}

export default App
