import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import useSWR from 'swr'
import {
  createAgentJob,
  getJob,
  getUploadScopes,
  streamJobEvents,
  uploadFile,
} from '../services/api'
import { useAuth } from '../context/AuthContext'

function getEventMessage(event: {
  type: string
  data: Record<string, unknown>
}) {
  switch (event.type) {
    case 'job_created':
      return 'Task created'

    case 'model_selected':
      return 'Selected model'

    case 'model_response':
      return 'Generated response'

    case 'plan_created':
      return 'Created execution plan'

    case 'step_started':
      return 'Started execution step'

    case 'tool_started':
      return 'Started tool'

    case 'tool_completed':
      return 'Completed tool'

    case 'observation':
      return 'Received tool observation'

    case 'approval_required':
      return 'Human approval required'

    case 'verification_passed':
      return 'Verification passed'

    case 'verification_failed':
      return 'Verification failed'

    case 'artifact_created':
      return 'Created artifact'

    case 'job_completed':
      return 'Task completed'

    default:
      return event.type.replace(/_/g, ' ')
  }
}

function NewTask() {
  const { token } = useAuth()
  const [task, setTask] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [scope, setScope] = useState('')

  const [events, setEvents] = useState<
    Array<{
      type: string
      data: Record<string, unknown>
    }>
  >([])

  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [jobId, setJobId] = useState<string | null>(null)
  const [submittedTask, setSubmittedTask] = useState<string | null>(null)
  const { data: scopeData } = useSWR(token ? ['upload-scopes', token] : null, ([, authToken]) => getUploadScopes(authToken))
  const scopes = scopeData?.scopes ?? []
  const { data: job, error: jobError } = useSWR(
    token && jobId ? ['job', jobId, token] : null,
    ([, id, authToken]) => getJob(id, authToken),
    {
      refreshInterval: 1200,
    },
  )
  useEffect(() => {
    if (!token || !jobId) return

    setEvents([])

    streamJobEvents(jobId, token, (event) => {
      setEvents((current) => [...current, event])
    }).catch((cause) => {
      setError(
        cause instanceof Error
          ? cause.message
          : 'Unable to connect to agent events',
      )
    })
  }, [jobId, token])



  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (!token || !task.trim()) return

    setSubmitting(true)
    setError(null)

    setJobId(null)

    try {
      const uploadedFileIds: string[] = []

      for (const file of files) {
        const uploaded = await uploadFile(
          file,
          scope || scopes[0] || 'private',
          token,
        )

        uploadedFileIds.push(uploaded.file_id)
      }

      const createdJob = await createAgentJob(
        task.trim(),
        uploadedFileIds,
        token,
      )

      setJobId(createdJob.job_id)

      setSubmittedTask(task.trim())

      setTask('')
      setFiles([])
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : 'Unable to submit task',
      )
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="new-task-page">
      <section className="new-task-header">
        <div>
          <p className="eyebrow">AGENT WORKSPACE</p>
          <h1>New Task</h1>
          <p className="dashboard-subtitle">
            Give Sovereign AI a task and it will work through it securely.
          </p>
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
                  <p>{job.final_answer}</p>
                ) : job ? (
                  <p>Agent status: {job.status}</p>
                ) : (
                  <p>Working on your task...</p>
                )}
              </div>
            </div>

            {events.length > 0 ? (
              <section className="activity-timeline">
                <p className="card-label">AGENT ACTIVITY</p>

                <div className="timeline-list">
                  {events
                    .filter((event) => event.type !== 'status_changed')
                    .map((event, index) => (
                      <div
                        className="timeline-item"
                        key={`${event.type}-${index}`}
                      >
                        <span className="timeline-dot" />
                        <span className="timeline-message">
                          {getEventMessage(event)}
                        </span>
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
            <p>
              Ask Sovereign AI to analyze documents, search authorized knowledge,
              or create a deliverable.
            </p>
          </div>
        )}

        <form className="chat-composer" onSubmit={handleSubmit}>
          <textarea
            id="task"
            value={task}
            onChange={(event) => setTask(event.target.value)}
            placeholder="Ask Sovereign AI..."
            required
          />

          <div className="composer-bottom">
            <div className="composer-left">
              <label className="attach-button" htmlFor="files">
                + Attach
              </label>

              <input
                id="files"
                type="file"
                multiple
                hidden
                onChange={(event) =>
                  setFiles(Array.from(event.target.files ?? []))
                }
              />

              {files.length > 0 ? (
                <span className="attachment-count">
                  {files.length} file{files.length === 1 ? '' : 's'}
                </span>
              ) : null}
            </div>

            <button
              className="send-button"
              type="submit"
              disabled={submitting}
            >
              {submitting ? 'Working…' : '↑'}
            </button>
          </div>
        </form>

        {files.length > 0 ? (
          <div className="selected-files">
            {files.map((file) => (
              <span
                className="selected-file"
                key={`${file.name}-${file.size}`}
              >
                {file.name}
              </span>
            ))}
          </div>
        ) : null}

        {scopes.length > 1 ? (
          <div className="scope-control">
            <label htmlFor="scope">File access</label>
            <select
              id="scope"
              value={scope || scopes[0]}
              onChange={(event) => setScope(event.target.value)}
            >
              {scopes.map((item) => (
                <option value={item} key={item}>
                  {item === 'everyone'
                    ? 'Everyone in lower tiers'
                    : item}
                </option>
              ))}
            </select>
          </div>
        ) : null}

        {error ? (
          <p className="form-error" role="alert">
            {error}
          </p>
        ) : null}

        {jobError ? (
          <p className="form-error" role="alert">
            {jobError.message}
          </p>
        ) : null}

        <p className="chat-disclaimer">
          Sovereign AI runs locally within your authorized environment.
        </p>
      </section>
    </main>
  )
}

export default NewTask
