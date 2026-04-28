import { type Event } from '../hooks/useWebSocket'
import { TaskPanel } from './TaskPanel'
import { AgentPanel } from './AgentPanel'
import { SystemPanel } from './SystemPanel'
import { ToolsPanel } from './ToolsPanel'

type Props = {
  logs: Event[]
}

export function Sidebar({ logs }: Props) {
  return (
    <aside className="sidebar">
      <TaskPanel logs={logs} />
      <AgentPanel logs={logs} />
      <SystemPanel />
      <ToolsPanel />
    </aside>
  )
}
