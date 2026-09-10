import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

function Sidebar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  function signOut() { logout(); navigate('/login', { replace: true }) }

  return (
    <aside className="sidebar">
      <h2 className="logo">Sovereign AI</h2>
      <p className="role-label">{user?.role ?? 'unknown'} tier</p>
      <nav className="sidebar-nav" aria-label="Main navigation">
        <NavLink to="/dashboard" className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>Dashboard</NavLink>
        <NavLink to="/new-task" className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>New Task</NavLink>
        <NavLink to="/tasks" className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>Tasks</NavLink>
        <NavLink to="/knowledge" className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>Knowledge Base</NavLink>
        <NavLink to="/artifacts" className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>Artifacts</NavLink>
      </nav>
      <button className="sign-out" type="button" onClick={signOut}>Sign out</button>
    </aside>
  )
}

export default Sidebar
