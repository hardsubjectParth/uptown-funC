import { useState } from 'react'
import type { FormEvent } from 'react'
import useSWR from 'swr'
import { getJob } from '../services/api'
import { useAuth } from '../context/AuthContext'

function Tasks() {
  const { token } = useAuth()
  const [jobId, setJobId] = useState('')
  const [activeJobId, setActiveJobId] = useState('')
  const { data: job, error, isLoading } = useSWR(token && activeJobId ? ['job', activeJobId, token] : null, ([, id, authToken]) => getJob(id, authToken), { refreshInterval: 1200 })
  function handleSubmit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setActiveJobId(jobId.trim()) }
  return <main><h1>Tasks</h1><p>Paste a job ID returned from New Task to follow its server-side status.</p>
    <form className="task-form" onSubmit={handleSubmit}><label htmlFor="job-id">Job ID</label><input id="job-id" value={jobId} onChange={(event) => setJobId(event.target.value)} required /><button className="new-task-button" type="submit">Track job</button></form>
    {isLoading ? <p>Loading job…</p> : null}{error ? <p className="form-error" role="alert">{error.message}</p> : null}
    {job ? <article className="task-card"><h2>{job.task}</h2><p>Status: <strong>{job.status}</strong></p>{job.final_answer ? <p>{job.final_answer}</p> : null}{job.error ? <p className="form-error">{job.error}</p> : null}<p className="helper-text">Auto-refreshing while this page is open.</p></article> : null}
  </main>
}
export default Tasks
