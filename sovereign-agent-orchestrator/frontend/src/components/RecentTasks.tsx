import { Link } from 'react-router-dom'
import useSWR from 'swr'
import { listJobs } from '../services/api'
import { useAuth } from '../context/AuthContext'

function RecentTasks() {
  const { token } = useAuth()
  const { data } = useSWR(token ? ['jobs', token] : null, ([, authToken]) => listJobs(authToken, 5), { refreshInterval: 5000 })
  const jobs = data?.data ?? []

  return (
    <section>
      <h2>Recent Tasks</h2>
      {jobs.length === 0 ? <p className="helper-text">No jobs yet.</p> : null}
      {jobs.map((job) => (
        <div className="task-card" key={job.job_id}>
          <h3>{job.task}</h3>
          <p>
            Status: <span className={`status ${job.status}`}>{job.status}</span>
            {job.model_name ? ` · ${job.model_name}` : ''}
          </p>
          <p className="helper-text"><Link to="/tasks">Open in Tasks</Link> · {job.job_id}</p>
        </div>
      ))}
    </section>
  )
}

export default RecentTasks
