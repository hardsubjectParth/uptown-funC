import { useState } from 'react'
import type { FormEvent } from 'react'
import useSWR from 'swr'
import { getJob, listJobs } from '../services/api'
import { useAuth } from '../context/AuthContext'

function Tasks() {
  const { token } = useAuth()
  const [jobId, setJobId] = useState('')
  const [activeJobId, setActiveJobId] = useState('')

  const { data: recent } = useSWR(token ? ['jobs', token] : null, ([, authToken]) => listJobs(authToken), { refreshInterval: 4000 })
  const { data: job, error, isLoading } = useSWR(
    token && activeJobId ? ['job', activeJobId, token] : null,
    ([, id, authToken]) => getJob(id, authToken),
    { refreshInterval: 1500 },
  )

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setActiveJobId(jobId.trim())
  }

  return (
    <main>
      <h1>Tasks</h1>
      <p>Select a recent job, or paste a job ID to follow its server-side status.</p>

      <section>
        <h2>Recent</h2>
        {(recent?.data ?? []).length === 0 ? <p className="helper-text">No jobs yet. Start one from New Task.</p> : null}
        {(recent?.data ?? []).map((item) => (
          <div
            className="task-card"
            key={item.job_id}
            role="button"
            tabIndex={0}
            style={{ cursor: 'pointer', outline: activeJobId === item.job_id ? '2px solid currentColor' : undefined }}
            onClick={() => { setActiveJobId(item.job_id); setJobId(item.job_id) }}
            onKeyDown={(event) => { if (event.key === 'Enter') { setActiveJobId(item.job_id); setJobId(item.job_id) } }}
          >
            <h3>{item.task}</h3>
            <p>
              <span className={`status ${item.status}`}>{item.status}</span>
              {item.task_type ? ` · ${item.task_type}` : ''}
              {item.model_name ? ` · ${item.model_name}` : ''}
              {item.verification_passed === true ? ' · verified ✓' : ''}
            </p>
            {item.artifacts.length ? <p className="helper-text">{item.artifacts.join(', ')}</p> : null}
            <p className="helper-text">{item.job_id}</p>
          </div>
        ))}
      </section>

      <form className="task-form" onSubmit={handleSubmit}>
        <label htmlFor="job-id">Job ID</label>
        <input id="job-id" value={jobId} onChange={(event) => setJobId(event.target.value)} required />
        <button className="new-task-button" type="submit">Track job</button>
      </form>

      {isLoading ? <p>Loading job…</p> : null}
      {error ? <p className="form-error" role="alert">{error.message}</p> : null}
      {job ? (
        <article className="task-card">
          <h2>{job.task}</h2>
          <p>
            Status: <strong>{job.status}</strong>
            {job.routing?.model_name ? ` · routed to ${job.routing.model_name}` : ''}
            {job.routing?.task_type ? ` (${job.routing.task_type})` : ''}
          </p>
          {job.verification ? (
            <ul>
              {Object.entries(job.verification.checks).map(([name, ok]) => (
                <li key={name}>{ok ? '✓' : '✗'} {name.replace(/_/g, ' ')}</li>
              ))}
            </ul>
          ) : null}
          {job.retrieval?.length ? (
            <details>
              <summary>Evidence used ({job.retrieval.length})</summary>
              {job.retrieval.map((hit, index) => (
                <p key={index} className="helper-text">{hit.source} · score {hit.score.toFixed(3)}</p>
              ))}
            </details>
          ) : null}
          {job.artifacts?.length ? <p>Artifacts: {job.artifacts.map((a) => a.name).join(', ')}</p> : null}
          {job.final_answer ? <p>{job.final_answer}</p> : null}
          {job.error ? <p className="form-error">{job.error}</p> : null}
          <p className="helper-text">Auto-refreshing while this page is open.</p>
        </article>
      ) : null}
    </main>
  )
}

export default Tasks
