import { NavLink } from 'react-router-dom'

function Sidebar() {
    return (
        <aside className="sidebar">
            <h2 className="logo">Sovereign AI</h2>

            <nav className="sidebar-nav">
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
        </aside >
    )
}

export default Sidebar