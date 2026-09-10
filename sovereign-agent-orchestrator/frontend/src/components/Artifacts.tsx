import { useState } from 'react'
import type { FormEvent } from 'react'
import useSWR from 'swr'
import { downloadArtifact, getJob } from '../services/api'
import { useAuth } from '../context/AuthContext'

function Artifacts() {
  const { token } = useAuth()
  const [jobId, setJobId] = useState('')
  const [activeJobId, setActiveJobId] = useState('')
  const [error, setError] = useState<string | null>(null)
  const { data: job } = useSWR(token && activeJobId ? ['artifacts', activeJobId, token] : null, ([, id, authToken]) => getJob(id, authToken))
  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setError(null); setActiveJobId(jobId.trim()) }
  async function save(name: string) {
    if (!token || !activeJobId) return
    try {
      const blob = await downloadArtifact(activeJobId, name, token)
      const url = URL.createObjectURL(blob); const anchor = document.createElement('a')
      anchor.href = url; anchor.download = name; anchor.click(); URL.revokeObjectURL(url)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Download failed') }
  }
  return <main><h1>Artifacts</h1><p>Download outputs from a job you are authorized to access.</p>
    <form className="task-form" onSubmit={submit}><label htmlFor="artifact-job-id">Job ID</label><input id="artifact-job-id" value={jobId} onChange={(event) => setJobId(event.target.value)} required /><button className="new-task-button" type="submit">View artifacts</button></form>
    {error ? <p className="form-error" role="alert">{error}</p> : null}
    <section>{job?.artifacts?.map((artifact) => <article className="task-card" key={artifact.name}><h2>{artifact.name}</h2><button type="button" onClick={() => save(artifact.name)}>Download</button></article>)}</section>
  </main>
}
export default Artifacts
