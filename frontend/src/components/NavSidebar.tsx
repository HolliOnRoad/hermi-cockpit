type Props = {
  currentView: string
  onNavigate: (view: string) => void
}

const navItems = [
  { id: 'overview', label: 'Uebersicht', icon: '\u25A3' },
  { id: 'agents', label: 'Agenten', icon: '\u25C8' },
  { id: 'memory', label: 'Memory', icon: '\u25A4' },
  { id: 'sessions', label: 'Sessions', icon: '\u25A6' },
]

export function NavSidebar({ currentView, onNavigate }: Props) {
  return (
    <nav className="nav-sidebar">
      {navItems.map((item) => (
        <button
          key={item.id}
          className={`nav-item${currentView === item.id ? ' nav-item--active' : ''}`}
          onClick={() => onNavigate(item.id)}
        >
          <span className="nav-icon">{item.icon}</span>
          <span className="nav-label">{item.label}</span>
        </button>
      ))}
    </nav>
  )
}
