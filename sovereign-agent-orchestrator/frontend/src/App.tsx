import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import Login from './components/Login'
import Shell from './components/shell/Shell'
import IntelligenceFeedPage from './pages/IntelligenceFeedPage'
import AgentTasksPage from './pages/AgentTasksPage'
import KnowledgeBasePage from './pages/KnowledgeBasePage'
import IngestKnowledgePage from './pages/IngestKnowledgePage'
import ArtifactsPage from './pages/ArtifactsPage'

function PageTransition({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -12 }}
      transition={{ duration: 0.22, ease: 'easeOut' }}
      className="flex min-h-0 flex-1 flex-col"
    >
      {children}
    </motion.div>
  )
}

function App() {
  const location = useLocation()

  return (
    <AnimatePresence mode="wait">
      <Routes location={location} key={location.pathname}>
        <Route path="/login" element={<Login />} />

        <Route path="/app/feed" element={<Shell><PageTransition><IntelligenceFeedPage /></PageTransition></Shell>} />
        <Route path="/app/feed/:id" element={<Shell><PageTransition><IntelligenceFeedPage /></PageTransition></Shell>} />
        <Route path="/app/tasks" element={<Shell><PageTransition><AgentTasksPage /></PageTransition></Shell>} />
        <Route path="/app/knowledge" element={<Shell><PageTransition><KnowledgeBasePage /></PageTransition></Shell>} />
        <Route path="/app/knowledge/ingest" element={<Shell><PageTransition><IngestKnowledgePage /></PageTransition></Shell>} />
        <Route path="/app/artifacts" element={<Shell><PageTransition><ArtifactsPage /></PageTransition></Shell>} />

        <Route path="/" element={<Navigate to="/app/feed" replace />} />
        <Route path="*" element={<Navigate to="/app/feed" replace />} />
      </Routes>
    </AnimatePresence>
  )
}

export default App
