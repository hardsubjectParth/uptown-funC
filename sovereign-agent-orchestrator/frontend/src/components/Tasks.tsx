import { useState } from 'react'
import type { FormEvent } from 'react'
import useSWR from 'swr'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { getJob, listJobs } from '../services/api'
import { useAuth } from '../context/AuthContext'
import ArtifactList from './ArtifactList'

const jobStages = ['queued', 'planning', 'acting', 'observing', 'verifying', 'delivering', 'done']

function formatStatus(status: string) {
  return status.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase())
}

function Tasks() {
  const { token } = useAuth()
  const [jobId, setJobId] = useState('')
  const [activeJobId, setActiveJobId] = useState('')

  const { data: recent } = useSWR(token ? ['jobs', token] : null, ([, authToken]) => listJobs(authToken), { refreshInterval: 4000 })
  const { data: job, error, isLoading } = useSWR(
    token && activeJobId ? ['job', activeJobId, token] : null,
    ([, id, authToken]) => getJob(id, authToken),
    { refreshInterval: 1200 },
  )

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setActiveJobId(jobId.trim())
  }

  const currentStage = job ? jobStages.indexOf(job.status) : -1

  return (
    <main className="dashboard">
      <section className="dashboard-header">
        <div>
          <p className="eyebrow">AGENT WORKSPACE</p>
          <h1>Tasks</h1>
          <p className="dashboard-subtitle">Select a recent job, or paste a job ID to follow its server-side status.</p>
        </div>
      </section>

      <section>
        <p className="card-label">RECENT</p>
        {(recent?.data ?? []).length === 0 ? <p className="helper-text">No jobs yet. Start one from New Task.</p> : null}
        {(recent?.data ?? []).map((item) => (
          <div
            className="task-card"
            key={item.job_id}
            role="button"
            tabIndex={0}
            style={{ cursor: 'pointer', outline: activeJobId === item.job_id ? '2px solid #C9A24D' : undefined }}
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

      <section className="task-tracker">
        <form className="task-form" onSubmit={handleSubmit}>
          <label htmlFor="job-id">Job ID</label>
          <div className="job-input-row">
            <input id="job-id" value={jobId} onChange={(event) => setJobId(event.target.value)} placeholder="Enter a job ID" required />
            <button className="new-task-button" type="submit">Track job</button>
          </div>
        </form>
      </section>

      {isLoading ? <p className="helper-text">Loading job…</p> : null}
      {error ? <p className="form-error" role="alert">{error.message}</p> : null}

      {job ? (
        <section className="job-details">
          <div className="job-header">
            <div>
              <p className="card-label">CURRENT TASK</p>
              <h2>{job.task}</h2>
            </div>
            <span className={`job-status ${job.status}`}>{formatStatus(job.status)}</span>
          </div>

          {job.routing?.model_name ? (
            <p className="helper-text">Routed to {job.routing.model_name}{job.routing.task_type ? ` (${job.routing.task_type})` : ''}</p>
          ) : null}

          {job.status === 'awaiting_approval' ? (
            <div className="approval-notice">
              <strong>Human approval required</strong>
              <p>This task is paused until an authorized reviewer approves it.</p>
            </div>
          ) : null}

          {job.status !== 'failed' && job.status !== 'cancelled' ? (
            <div className="job-progress">
              {jobStages.map((stage, index) => {
                const completed = currentStage > index
                const active = currentStage === index
                return (
                  <div className={`job-stage ${completed ? 'completed' : ''} ${active ? 'active' : ''}`} key={stage}>
                    <span className="stage-dot" />
                    <span>{formatStatus(stage)}</span>
                  </div>
                )
              })}
            </div>
          ) : null}

          {job.verification ? (
            <div className="job-result">
              <p className="card-label">VERIFICATION</p>
              {Object.entries(job.verification.checks).map(([name, ok]) => (
                <p key={name}>{ok ? '✓' : '✗'} {name.replace(/_/g, ' ')}</p>
              ))}
            </div>
          ) : null}

          {job.retrieval?.length ? (
            <details className="job-result">
              <summary className="card-label">EVIDENCE USED ({job.retrieval.length})</summary>
              {job.retrieval.map((hit, index) => <p key={index}>{hit.source} · score {hit.score.toFixed(3)}</p>)}
            </details>
          ) : null}

          {job.final_answer ? (
            <div className="job-result">
              <p className="card-label">RESULT</p>
              <div className="markdown"><Markdown remarkPlugins={[remarkGfm]}>{job.final_answer}</Markdown></div>
            </div>
          ) : null}

          {job.artifacts?.length ? (
            <div className="job-result">
              <p className="card-label">ARTIFACTS</p>
              <ArtifactList jobId={job.job_id} artifacts={job.artifacts} />
            </div>
          ) : null}

          {job.error ? (
            <div className="job-error">
              <p className="card-label">ERROR</p>
              <p>{job.error}</p>
            </div>
          ) : null}

          <p className="helper-text">Auto-refreshing while this page is open.</p>
        </section>
      ) : null}
    </main>
  )
}

export default Tasks
