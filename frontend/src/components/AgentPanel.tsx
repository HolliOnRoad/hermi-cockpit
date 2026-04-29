import { type Event } from '../hooks/useWebSocket'

type Props = {
  logs: Event[]
}

type AgentDef = {
  name: string
  key: string
}

const agents: AgentDef[] = [
  { name: 'Orchestrator', key: 'orchestrator' },
  { name: 'Researcher', key: 'researcher' },
  { name: 'Obsidian', key: 'obsidian' },
  { name: 'Tool Agent', key: 'tool-agent' },
  { name: 'Planner', key: 'planner' },
]

function deriveAgentStates(logs: Event[]): Map<string, 'active' | 'idle' | 'done'> {
  const states = new Map<string, 'active' | 'idle' | 'done'>()
  agents.forEach((a) => states.set(a.key, 'idle'))

  for (let i = logs.length - 1; i >= 0; i--) {
    const e = logs[i]
    if (e.type !== 'agent' || !e.meta?.agent) continue
    const agentName = (e.meta.agent as string).toLowerCase()
    const matched = agents.find(
      (a) => agentName.includes(a.key) || a.key.includes(agentName),
    )
    if (!matched) continue
    if (states.get(matched.key) !== 'idle') continue

    if (e.message.toLowerCase().includes('beendet')) {
      states.set(matched.key, 'done')
    } else {
      states.set(matched.key, 'active')
    }
  }
  return states
}

const statusPill: Record<string, { label: string; cls: string }> = {
  active: { label: 'Active', cls: 'pill-active' },
  idle: { label: 'Idle', cls: 'pill-idle' },
  done: { label: 'Done', cls: 'pill-done' },
}

export function AgentPanel({ logs }: Props) {
  const agentStates = deriveAgentStates(logs)
  const allIdle = Array.from(agentStates.values()).every((s) => s === 'idle')

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Agents</span>
        {allIdle && <span className="agent-summary-pill">Alle bereit</span>}
      </div>
      <div className="panel-body">
        <div className="agent-list">
          {agents.map((agent) => {
            const state = agentStates.get(agent.key) ?? 'idle'
            const p = statusPill[state]
            return (
              <div key={agent.key} className="agent-row">
                <span className="agent-name">{agent.name}</span>
                <span className={`pill ${p.cls}`}>{p.label}</span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
