import { useState } from 'react'
import { useWebSocket } from './hooks/useWebSocket'
import { useDragDropGuard } from './hooks/useDragDropGuard'
import { TopBar } from './components/TopBar'
import { Terminal } from './components/Terminal'
import { Sidebar } from './components/Sidebar'
import { DebugBar } from './components/DebugBar'
import { QueryInput } from './components/QueryInput'
import { NavSidebar } from './components/NavSidebar'
import { MemoryView } from './components/MemoryView'
import { SessionsView } from './components/SessionsView'
import { AgentsView } from './components/AgentsView'
import { OutcomeCard } from './components/OutcomeCard'

function App() {
  const { status, logs, sendTestEvent } = useWebSocket()
  const [view, setView] = useState('overview')

  useDragDropGuard()

  return (
    <div className="cockpit-container">
      <TopBar
        status={status}
        eventCount={logs.length}
        onTestEvent={sendTestEvent}
      />

      <div className="cockpit-body">
        <NavSidebar currentView={view} onNavigate={setView} />

        <div className="main-content">
          {view === 'overview' && (
            <main className="main">
              <section className="terminal-section">
                <OutcomeCard logs={logs} />
                <Terminal logs={logs} status={status} />
                <QueryInput logs={logs} />
              </section>
              <Sidebar logs={logs} />
            </main>
          )}
          {view === 'memory' && <MemoryView />}
          {view === 'sessions' && <SessionsView />}
          {view === 'agents' && <AgentsView logs={logs} />}
        </div>
      </div>

      <DebugBar status={status} eventCount={logs.length} />
    </div>
  )
}

export default App
