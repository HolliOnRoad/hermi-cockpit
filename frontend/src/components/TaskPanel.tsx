import { type Event } from '../hooks/useWebSocket'

type Props = {
  logs: Event[]
}

function deriveTaskState(logs: Event[]) {
  const lastTask = logs.find((e) => e.type === 'task')
  const lastDone = logs.find((e) => e.type === 'done')
  const lastError = logs.find((e) => e.type === 'error')
  const lastTaskEvent = logs.find((e) => ['task', 'done', 'error', 'agent', 'tool'].includes(e.type))

  const taskName = lastTask?.message?.replace('Task gestartet: ', '') ?? null
  const doneResult = lastDone?.meta?.result as string | undefined
  const errorMsg = lastError?.message ?? null

  let status: 'idle' | 'running' | 'done' | 'error' = 'idle'
  if (lastError && (!lastTask || logs.indexOf(lastError) < logs.indexOf(lastTask))) {
    // Error came after task — but check that it's actually the most recent terminal event
  }
  if (lastDone && lastTask && logs.indexOf(lastDone) < logs.indexOf(lastTask)) {
    status = 'done'
  } else if (lastError && lastTask && logs.indexOf(lastError) < logs.indexOf(lastTask)) {
    status = 'error'
  } else if (lastTask && (!lastDone || logs.indexOf(lastTask) < logs.indexOf(lastDone)) && (!lastError || logs.indexOf(lastTask) < logs.indexOf(lastError))) {
    status = 'running'
  } else if (lastDone) {
    status = 'done'
  }

  return { taskName, doneResult, errorMsg, status, lastEvent: lastTaskEvent }
}

const statusLabel: Record<string, string> = {
  idle: 'Idle',
  running: 'Running',
  done: 'Completed',
  error: 'Error',
}

export function TaskPanel({ logs }: Props) {
  const { taskName, doneResult, errorMsg, status } = deriveTaskState(logs)

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Current Task</span>
        <span className={`pill pill-${status}`}>{statusLabel[status]}</span>
      </div>
      <div className="panel-body">
        {taskName ? (
          <div className="task-info">
            <div className="task-name">{taskName}</div>
            {status === 'done' && doneResult && (
              <div className="task-result">{doneResult}</div>
            )}
            {status === 'error' && errorMsg && (
              <div className="task-error">{errorMsg}</div>
            )}
            {status === 'running' && (
              <div className="task-result muted">In progress...</div>
            )}
          </div>
        ) : (
          <div className="panel-empty">No active task</div>
        )}
        <div className="task-meta">
          <span className="meta-label">Events</span>
          <span className="meta-value">{logs.length}</span>
        </div>
        <div className="task-meta">
          <span className="meta-label">Source</span>
          <span className="meta-value">Live</span>
        </div>
      </div>
    </div>
  )
}
