import { useState } from 'react'
import type { FormEvent } from 'react'
import { useJob } from '../hooks/useJob'
import ArtifactCard from '../components/shared/ArtifactCard'

function ArtifactsPage() {
  const [jobId, setJobId] = useState('')
  const [activeJobId, setActiveJobId] = useState('')
  const { job, error } = useJob(activeJobId || undefined)
  const [layout, setLayout] = useState<'grid' | 'list'>('list')

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setActiveJobId(jobId.trim())
  }

  return (
    <main className="flex-1 overflow-y-auto px-8 py-8">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-foreground">Generated Artifacts</h1>
        <div className="flex gap-1">
          <button type="button" onClick={() => setLayout('list')} className={`label-micro px-2.5 py-1.5 ${layout === 'list' ? 'bg-surface-raised text-accent' : 'text-muted-foreground'}`}>List</button>
          <button type="button" onClick={() => setLayout('grid')} className={`label-micro px-2.5 py-1.5 ${layout === 'grid' ? 'bg-surface-raised text-accent' : 'text-muted-foreground'}`}>Grid</button>
        </div>
      </div>

      <p className="mt-2 text-sm text-muted-foreground">
        Artifacts also appear inline on Intelligence Feed and Agent Tasks right after a job finishes — this page looks one up by job ID.
      </p>

      <form onSubmit={submit} className="border-hairline mt-5 flex max-w-xl items-center gap-2 bg-surface px-3 py-2">
        <input
          value={jobId}
          onChange={(event) => setJobId(event.target.value)}
          placeholder="Job ID"
          required
          className="flex-1 bg-transparent py-1 font-mono text-sm text-foreground outline-none placeholder:text-muted-foreground"
        />
        <button type="submit" className="bg-accent px-3 py-1.5 text-xs font-semibold text-accent-foreground">View Artifacts</button>
      </form>

      {error ? <p className="mt-3 text-xs text-danger">{error.message}</p> : null}
      {job && !job.artifacts.length ? <p className="mt-3 text-sm text-muted-foreground">This job has no artifacts.</p> : null}

      {job?.artifacts?.length ? (
        <div className={`mt-5 ${layout === 'grid' ? 'grid grid-cols-3 gap-3' : 'flex flex-col gap-2'} max-w-3xl`}>
          {job.artifacts.map((artifact) => (
            <ArtifactCard key={artifact.artifact_id} jobId={job.job_id} artifact={artifact} layout={layout} />
          ))}
        </div>
      ) : null}
    </main>
  )
}

export default ArtifactsPage
