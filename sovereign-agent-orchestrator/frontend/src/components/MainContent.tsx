import { useNavigate } from 'react-router-dom'
import RecentArtifacts from './RecentArtifacts'
import RecentTasks from './RecentTasks'
import { useEffect } from 'react'
import { healthCheck } from '../services/api'


function MainContent() {
    useEffect(() => {
        healthCheck()
            .then((data) => {
                console.log('Backend:', data)
            })
            .catch((error) => {
                console.error('Backend connection failed:', error)
            })
    }, [])
    const navigate = useNavigate()
    return (
        <main>
            <h1>Welcome to Sovereign AI</h1>
            <p>Start a new task or continue working on an existing one.</p>

            <button
                className="new-task-button"
                onClick={() => navigate('/new-task')}
            >
                + New Task
            </button>

            <RecentTasks />

            <RecentArtifacts />
        </main>
    )
}

export default MainContent