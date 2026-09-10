import { Navigate, Route, Routes } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import MainContent from './components/MainContent'
import NewTask from './components/NewTask'
import Tasks from './components/Tasks'
import KnowledgeBase from './components/KnowledgeBase'
import Artifacts from './components/Artifacts'
import Login from './components/Login'
import ProtectedRoute from './components/ProtectedRoute'

function AuthenticatedLayout({ children }: { children: React.ReactNode }) {
  return <ProtectedRoute><div className="app"><Sidebar />{children}</div></ProtectedRoute>
}

function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="/login" element={<Login />} />
      <Route path="/dashboard" element={<AuthenticatedLayout><MainContent /></AuthenticatedLayout>} />
      <Route path="/new-task" element={<AuthenticatedLayout><NewTask /></AuthenticatedLayout>} />
      <Route path="/tasks" element={<AuthenticatedLayout><Tasks /></AuthenticatedLayout>} />
      <Route path="/knowledge" element={<AuthenticatedLayout><KnowledgeBase /></AuthenticatedLayout>} />
      <Route path="/artifacts" element={<AuthenticatedLayout><Artifacts /></AuthenticatedLayout>} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}

export default App
