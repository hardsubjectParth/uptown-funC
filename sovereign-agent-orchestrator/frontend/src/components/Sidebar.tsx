import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

function Sidebar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  function signOut() {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <h2 className="logo">Sovereign AI</h2>
        <p className="brand-subtitle">WORKBENCH</p>
      </div>


      <nav className="sidebar-nav" aria-label="Main navigation">
        <NavLink
          to="/dashboard"
          className={({ isActive }) =>
            isActive ? 'nav-item active' : 'nav-item'
          }
        >
          Dashboard
        </NavLink>

        <NavLink
          to="/new-task"
          className={({ isActive }) =>
            isActive ? 'nav-item active' : 'nav-item'
          }
        >
          New Task
        </NavLink>

        <NavLink
          to="/tasks"
          className={({ isActive }) =>
            isActive ? 'nav-item active' : 'nav-item'
          }
        >
          Tasks
        </NavLink>

        <NavLink
          to="/knowledge"
          className={({ isActive }) =>
            isActive ? 'nav-item active' : 'nav-item'
          }
        >
          Knowledge Base
        </NavLink>

        <NavLink
          to="/artifacts"
          className={({ isActive }) =>
            isActive ? 'nav-item active' : 'nav-item'
          }
        >
          Artifacts
        </NavLink>
      </nav>

      <div className="sidebar-bottom">
        <div className="sidebar-system">
          <span className="status-dot online" />
          <span>System online</span>
        </div>

        <div className="user-card">
          <div className="user-card-role">
            {user?.role ?? 'unknown'} tier
          </div>
          <div className="user-card-tenant">
            {user?.tenant_id ?? 'unknown tenant'}
          </div>
        </div>

        <button className="sign-out" type="button" onClick={signOut}>
          Sign out
        </button>
      </div>
    </aside>
  )
}

export default Sidebar