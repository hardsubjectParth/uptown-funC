import { useState } from 'react'
import type { FormEvent } from 'react'
import useSWR from 'swr'

import { getJob } from '../services/api'
import { useAuth } from '../context/AuthContext'

const jobStages = [
  'queued',
  'planning',
  'acting',
  'observing',
  'verifying',
  'delivering',
  'done',
]

function formatStatus(status: string) {
  return status.replace('_', ' ').replace(/\b\w/g, (char) => char.toUpperCase())
}

function Tasks() {
  const { token } = useAuth()

  const [jobId, setJobId] = useState('')
  const [activeJobId, setActiveJobId] = useState('')

  const {
    data: job,
    error,
    isLoading,
  } = useSWR(
    token && activeJobId ? ['job', activeJobId, token] : null,
    ([, id, authToken]) => getJob(id, authToken),
    {
      refreshInterval: 1200,
    },
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
          <p className="dashboard-subtitle">
            Track an agent job and monitor its progress in real time.
          </p>
        </div>
      </section>

      <section className="task-tracker">
        <form className="task-form" onSubmit={handleSubmit}>
          <label htmlFor="job-id">Job ID</label>

          <div className="job-input-row">
            <input
              id="job-id"
              value={jobId}
              onChange={(event) => setJobId(event.target.value)}
              placeholder="Enter a job ID"
              required
            />

            <button className="new-task-button" type="submit">
              Track job
            </button>
          </div>
        </form>
      </section>

      {isLoading ? (
        <p className="helper-text">Loading job...</p>
      ) : null}

      {error ? (
        <p className="form-error" role="alert">
          {error.message}
        </p>
      ) : null}

      {job ? (
        <section className="job-details">
          <div className="job-header">
            <div>
              <p className="card-label">CURRENT TASK</p>
              <h2>{job.task}</h2>
            </div>

            <span className={`job-status ${job.status}`}>
              {formatStatus(job.status)}
            </span>
          </div>

          {job.status === 'awaiting_approval' ? (
            <div className="approval-notice">
              <strong>Human approval required</strong>
              <p>
                This task is paused until an authorized reviewer approves it.
              </p>
            </div>
          ) : null}

          {job.status !== 'failed' && job.status !== 'cancelled' ? (
            <div className="job-progress">
              {jobStages.map((stage, index) => {
                const completed = currentStage > index
                const active = currentStage === index

                return (
                  <div
                    className={`job-stage ${
                      completed ? 'completed' : ''
                    } ${active ? 'active' : ''}`}
                    key={stage}
                  >
                    <span className="stage-dot" />
                    <span>{formatStatus(stage)}</span>
                  </div>
                )
              })}
            </div>
          ) : null}

          {job.final_answer ? (
            <div className="job-result">
              <p className="card-label">RESULT</p>
              <p>{job.final_answer}</p>
            </div>
          ) : null}

          {job.error ? (
            <div className="job-error">
              <p className="card-label">ERROR</p>
              <p>{job.error}</p>
            </div>
          ) : null}

          <p className="helper-text">
            Updating automatically while this page is open.
          </p>
        </section>
      ) : null}
    </main>
  )
}

export default Tasks