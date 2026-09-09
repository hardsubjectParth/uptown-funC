import { Routes, Route, Navigate } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import MainContent from './components/MainContent'
import NewTask from './components/NewTask'
import Tasks from './components/Tasks'
import KnowledgeBase from './components/KnowledgeBase'
import Artifacts from './components/Artifacts'
import Login from './components/Login'
import ProtectedRoute from './components/ProtectedRoute'

function App() {
  return (
    <div className="app">
      <Sidebar />

      <Routes>
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="/login" element={<Login />} />

        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <MainContent />
            </ProtectedRoute>
          }
        />
        <Route path="/new-task" element={<NewTask />} />
        <Route path="/tasks" element={<Tasks />} />
        <Route path="/knowledge" element={<KnowledgeBase />} />
        <Route path="/artifacts" element={<Artifacts />} />
      </Routes>
    </div>
  )
}

export default App