import { LayoutDashboard, Bot, Brain, Clock } from 'lucide-react'

type Props = {
  currentView: string
  onNavigate: (view: string) => void
}

const navItems = [
  { id: 'overview', label: 'Uebersicht', Icon: LayoutDashboard },
  { id: 'agents', label: 'Agenten', Icon: Bot },
  { id: 'memory', label: 'Memory', Icon: Brain },
  { id: 'sessions', label: 'Sessions', Icon: Clock },
]

export function NavSidebar({ currentView, onNavigate }: Props) {
  return (
    <nav className="nav-sidebar">
      {navItems.map(({ id, label, Icon }) => (
        <button
          key={id}
          className={`nav-item${currentView === id ? ' nav-item--active' : ''}`}
          onClick={() => onNavigate(id)}
        >
          <Icon className="nav-icon" size={16} />
          <span className="nav-label">{label}</span>
        </button>
      ))}
    </nav>
  )
}
