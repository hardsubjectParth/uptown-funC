import { useState } from 'react'
import type { FormEvent } from 'react'
import useSWR from 'swr'
import { getJob } from '../services/api'
import { useAuth } from '../context/AuthContext'
import ArtifactList from './ArtifactList'

function Artifacts() {
  const { token } = useAuth()
  const [jobId, setJobId] = useState('')
  const [activeJobId, setActiveJobId] = useState('')
  const { data: job, error } = useSWR(token && activeJobId ? ['artifacts', activeJobId, token] : null, ([, id, authToken]) => getJob(id, authToken))
  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setActiveJobId(jobId.trim()) }
  return <main><h1>Artifacts</h1><p>Download outputs from a job you are authorized to access. Artifacts also show inline on New Task and Tasks right after a job finishes — this page is for looking one up by ID later.</p>
    <form className="task-form" onSubmit={submit}><label htmlFor="artifact-job-id">Job ID</label><input id="artifact-job-id" value={jobId} onChange={(event) => setJobId(event.target.value)} required /><button className="new-task-button" type="submit">View artifacts</button></form>
    {error ? <p className="form-error" role="alert">{error.message}</p> : null}
    {job && !job.artifacts?.length ? <p className="helper-text">This job has no artifacts.</p> : null}
    {job?.artifacts?.length ? <ArtifactList jobId={activeJobId} artifacts={job.artifacts} /> : null}
  </main>
}
export default Artifacts
