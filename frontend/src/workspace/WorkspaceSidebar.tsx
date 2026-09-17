import { useEffect, useState } from 'react'
import type { ModuleKey } from './catalog'
import lightLogo from '../assets/hiatlas-light.png'
import darkLogo from '../assets/hiatlas-dark.png'

type NavigationModule = {id: ModuleKey; label: string; icon: string; children: string[]}
type Props = {
  theme: string
  menuOpen: boolean
  active: ModuleKey
  section: string
  modules: NavigationModule[]
  profile: {name: string; code: string}
  onNavigate: (module: ModuleKey, section?: string) => void
  onLogout: () => void
}

export default function WorkspaceSidebar({theme, menuOpen, active, section, modules, profile, onNavigate, onLogout}: Props) {
  const [compact, setCompact] = useState(() => {
    try { return localStorage.getItem('hiatlas-menu-mode') === 'icons' }
    catch { return false }
  })
  useEffect(() => {
    try { localStorage.setItem('hiatlas-menu-mode', compact ? 'icons' : 'labels') }
    catch { /* Navigation remains available without local storage. */ }
  }, [compact])

  return <aside className={`ws-sidebar ${menuOpen ? 'is-open' : ''} ${compact ? 'is-compact' : ''}`}>
    <div className="ws-brand"><img src={theme === 'light' ? lightLogo : darkLogo} alt="HiAtlas — Supply Chain Intelligence"/><span>WORKSPACE</span></div>
    <button className="ws-menu-mode" aria-label="Menu: Somente ícones" aria-pressed={compact} onClick={() => setCompact(value => !value)}>
      <span aria-hidden="true">{compact ? '✓' : '▦'}</span><span>Somente ícones</span>
    </button>
    <nav aria-label="Módulos HiAtlas">
      {modules.map((module, index) => <div key={module.id}>
        {index === 1 && <div className="ws-nav-caption">OPERAÇÃO</div>}
        <button className={`ws-nav-item ${active === module.id ? 'selected' : ''}`} aria-label={module.label}
          aria-expanded={module.children.length ? active === module.id : undefined}
          title={compact ? module.label : undefined} onClick={() => onNavigate(module.id)}>
          <i aria-hidden="true">{module.icon}</i><span className="ws-nav-label" aria-hidden="true">{module.label}</span>
          {module.children.length > 0 && <span className="ws-chevron" aria-hidden="true">⌄</span>}
        </button>
        {active === module.id && module.children.length > 0 && <div className="ws-subnav">
          {module.children.map(child => <button key={child} aria-current={section === child ? 'page' : undefined} onClick={() => onNavigate(module.id, child)}>{child}</button>)}
        </div>}
      </div>)}
    </nav>
    <div className="ws-profile"><span className="ws-avatar" title={profile.name}>{profile.name.slice(0,2).toUpperCase()}</span><div><strong>{profile.name}</strong><small>{profile.code} · Demonstração</small></div><button onClick={onLogout} aria-label="Sair" title="Sair">↪</button></div>
  </aside>
}
