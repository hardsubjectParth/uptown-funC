import { useRef, useState } from 'react'
import type { FormEvent } from 'react'
import useSWR from 'swr'
import { createAgentJob, getUploadScopes, streamJobEvents, uploadFile } from '../services/api'
import type { JobEvent } from '../services/api'
import { useAuth } from '../context/AuthContext'

const EVENT_LABELS: Record<string, string> = {
  job_created: 'Task created',
  status_changed: 'Status changed',
  model_selected: 'Selected model',
  model_fallback: 'Model unavailable, falling back',
  model_error: 'Model call failed',
  model_response: 'Generated response',
  plan_created: 'Created execution plan',
  replanning: 'Revising plan',
  step_started: 'Started execution step',
  step_completed: 'Finished execution step',
  tool_started: 'Started tool',
  tool_completed: 'Completed tool',
  observation: 'Collected tool output',
  approval_required: 'Waiting for human approval',
  approval_approved: 'Approval granted',
  approval_rejected: 'Approval rejected',
  verification_passed: 'Verification passed',
  verification_failed: 'Verification failed',
  artifact_created: 'Saved artifact',
  job_completed: 'Task finished',
  job_cancelled: 'Task cancelled',
}

function describeEvent(event: JobEvent) {
  const label = EVENT_LABELS[event.type] ?? event.type.replace(/_/g, ' ')
  const detail =
    (event.data.status as string) ||
    (event.data.model_name as string) ||
    (event.data.model_id as string) ||
    (event.data.tool as string) ||
    (event.data.name as string) ||
    ''
  return detail ? `${label} · ${detail}` : label
}

function NewTask() {
  const { token } = useAuth()
  const [task, setTask] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [scope, setScope] = useState('')
  const [result, setResult] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [liveEvents, setLiveEvents] = useState<JobEvent[]>([])
  const abortRef = useRef<AbortController | null>(null)
  const { data: scopeData } = useSWR(token ? ['upload-scopes', token] : null, ([, authToken]) => getUploadScopes(authToken))
  const scopes = scopeData?.scopes ?? []

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!token || !task.trim()) return
    abortRef.current?.abort()
    setSubmitting(true); setError(null); setResult(null); setLiveEvents([])
    try {
      const fileIds: string[] = []
      for (const file of files) {
        const uploaded = await uploadFile(file, scope || scopes[0] || 'private', token)
        fileIds.push(uploaded.file_id)
      }
      const job = await createAgentJob(task.trim(), token, fileIds)
      setResult(`Job ${job.job_id} is ${job.status}. Follow-up detail below, or find it later in Tasks.`)
      setTask(''); setFiles([])

      const controller = new AbortController()
      abortRef.current = controller
      streamJobEvents(job.job_id, token, (streamed) => setLiveEvents((prev) => [...prev, streamed]), controller.signal).catch((cause) => {
        if (controller.signal.aborted) return
        setError(cause instanceof Error ? cause.message : 'Live progress stream ended unexpectedly')
      })
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to submit task')
    } finally { setSubmitting(false) }
  }

  return <main>
    <h1>New Task</h1><p>Create a job and upload knowledge into your allowed tier.</p>
    <form className="task-form" onSubmit={handleSubmit}>
      <label htmlFor="task">Task description</label>
      <textarea id="task" value={task} onChange={(event) => setTask(event.target.value)} placeholder="What do you want the agent to do?" required />
      <label htmlFor="files">Knowledge files</label>
      <input id="files" type="file" multiple onChange={(event) => setFiles(Array.from(event.target.files ?? []))} />
      {scopes.length > 1 ? <><label htmlFor="scope">Who can use these files?</label><select id="scope" value={scope || scopes[0]} onChange={(event) => setScope(event.target.value)}>{scopes.map((item) => <option value={item} key={item}>{item === 'everyone' ? 'Everyone in lower tiers' : item}</option>)}</select></> : <p className="helper-text">Files are stored in the lower tier for your role.</p>}
      {files.map((file) => <p key={`${file.name}-${file.size}`}>{file.name}</p>)}
      {error ? <p className="form-error" role="alert">{error}</p> : null}
      {result ? <p className="form-success" role="status">{result}</p> : null}
      <button className="new-task-button" type="submit" disabled={submitting}>{submitting ? 'Submitting…' : 'Run Task'}</button>
    </form>
    {liveEvents.length ? (
      <section aria-live="polite">
        <h2>Live progress</h2>
        <ul className="event-log">
          {liveEvents.map((event) => (
            <li key={event.event_id}>
              <span className="helper-text">{new Date(event.timestamp).toLocaleTimeString()}</span> — {describeEvent(event)}
            </li>
          ))}
        </ul>
      </section>
    ) : null}
  </main>
}

export default NewTask
