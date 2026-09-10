import { useNavigate } from 'react-router-dom'
import useSWR from 'swr'
import { healthCheck } from '../services/api'
import { useAuth } from '../context/AuthContext'

function MainContent() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const { data, error } = useSWR('health', healthCheck, { revalidateOnFocus: false })
  return <main>
    <h1>Welcome to Sovereign AI</h1>
    <p>Signed in as <strong>{user?.role}</strong>. Your requests are routed only to authorized pgvector tiers.</p>
    <p className={error ? 'form-error' : 'helper-text'}>{error ? 'FastAPI backend is unavailable.' : data?.status === 'ok' ? 'FastAPI backend connected.' : 'Checking backend…'}</p>
    <button className="new-task-button" onClick={() => navigate('/new-task')}>New Task</button>
  </main>
}
export default MainContent
