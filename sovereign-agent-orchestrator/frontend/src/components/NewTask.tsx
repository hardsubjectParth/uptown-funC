import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import useSWR from 'swr'
import Markdown from 'react-markdown'
import { createAgentJob, getJob, getUploadScopes, streamJobEvents, uploadFile } from '../services/api'
import type { JobEvent } from '../services/api'
import { useAuth } from '../context/AuthContext'
import ArtifactList from './ArtifactList'

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
  job_completed: 'Task completed',
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
  const [events, setEvents] = useState<JobEvent[]>([])
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [jobId, setJobId] = useState<string | null>(null)
  const [submittedTask, setSubmittedTask] = useState<string | null>(null)
  const { data: scopeData } = useSWR(token ? ['upload-scopes', token] : null, ([, authToken]) => getUploadScopes(authToken))
  const scopes = scopeData?.scopes ?? []
  const { data: job } = useSWR(
    token && jobId ? ['job', jobId, token] : null,
    ([, id, authToken]) => getJob(id, authToken),
    { refreshInterval: 1200 },
  )

  useEffect(() => {
    if (!token || !jobId) return
    setEvents([])
    const controller = new AbortController()
    streamJobEvents(jobId, token, (event) => setEvents((current) => [...current, event]), controller.signal).catch((cause) => {
      if (controller.signal.aborted) return
      setError(cause instanceof Error ? cause.message : 'Unable to connect to agent events')
    })
    return () => controller.abort()
  }, [jobId, token])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!token || !task.trim()) return
    setSubmitting(true); setError(null); setJobId(null)
    try {
      const uploadedFileIds: string[] = []
      for (const file of files) {
        const uploaded = await uploadFile(file, scope || scopes[0] || 'private', token)
        uploadedFileIds.push(uploaded.file_id)
      }
      const createdJob = await createAgentJob(task.trim(), token, uploadedFileIds)
      setJobId(createdJob.job_id)
      setSubmittedTask(task.trim())
      setTask(''); setFiles([])
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to submit task')
    } finally { setSubmitting(false) }
  }

  return (
    <main className="new-task-page">
      <section className="new-task-header">
        <div>
          <p className="eyebrow">AGENT WORKSPACE</p>
          <h1>New Task</h1>
          <p className="dashboard-subtitle">Give Sovereign AI a task and it will work through it securely.</p>
        </div>
      </section>

      <section className="task-chat">
        {submittedTask ? (
          <>
            <div className="conversation">
              <div className="message user-message">
                <div className="message-label">You</div>
                <p>{submittedTask}</p>
              </div>

              <div className="message assistant-message">
                <div className="message-label">Sovereign AI</div>
                {job?.final_answer ? (
                  <div className="markdown"><Markdown>{job.final_answer}</Markdown></div>
                ) : job?.error ? (
                  <p>{job.error}</p>
                ) : job ? (
                  <p>Agent status: {job.status}</p>
                ) : (
                  <p>Working on your task…</p>
                )}
              </div>

              {job?.artifacts?.length ? <ArtifactList jobId={jobId!} artifacts={job.artifacts} /> : null}
            </div>

            {events.length > 0 ? (
              <section className="activity-timeline">
                <p className="card-label">AGENT ACTIVITY</p>
                <div className="timeline-list">
                  {events.filter((event) => event.type !== 'status_changed').map((event) => (
                    <div className="timeline-item" key={event.event_id}>
                      <span className="timeline-dot" />
                      <span className="timeline-message">{describeEvent(event)}</span>
                      <span className="timeline-time">{new Date(event.timestamp).toLocaleTimeString()}</span>
                    </div>
                  ))}
                </div>
              </section>
            ) : null}
          </>
        ) : (
          <div className="chat-empty-state">
            <div className="chat-mark">S</div>
            <h2>What can I help you with?</h2>
            <p>Ask Sovereign AI to analyze documents, search authorized knowledge, or create a deliverable.</p>
          </div>
        )}

        <form className="chat-composer" onSubmit={handleSubmit}>
          <textarea
            value={task}
            onChange={(event) => setTask(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                event.currentTarget.form?.requestSubmit()
              }
            }}
            placeholder="What would you like Sovereign AI to do?"
          />

          <div className="composer-bottom">
            <div className="composer-left">
              <label className="attach-button" htmlFor="files">+ Attach</label>
              <input id="files" type="file" multiple hidden onChange={(event) => setFiles(Array.from(event.target.files ?? []))} />
              {files.length > 0 ? <span className="attachment-count">{files.length} file{files.length === 1 ? '' : 's'}</span> : null}
            </div>

            <button className="send-button" type="submit" disabled={submitting}>{submitting ? '…' : '↑'}</button>
          </div>
        </form>

        {files.length > 0 ? (
          <div className="selected-files">
            {files.map((file) => <span className="selected-file" key={`${file.name}-${file.size}`}>{file.name}</span>)}
          </div>
        ) : null}

        {scopes.length > 1 ? (
          <div className="scope-control">
            <label htmlFor="scope">File access</label>
            <select id="scope" value={scope || scopes[0]} onChange={(event) => setScope(event.target.value)}>
              {scopes.map((item) => <option value={item} key={item}>{item === 'everyone' ? 'Everyone in lower tiers' : item}</option>)}
            </select>
          </div>
        ) : null}

        {error ? <p className="form-error" role="alert">{error}</p> : null}

        <p className="chat-disclaimer">Sovereign AI runs locally within your authorized environment.</p>
      </section>
    </main>
  )
}

export default NewTask
