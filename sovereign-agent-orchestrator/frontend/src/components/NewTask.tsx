import { useState } from 'react'
import type { FormEvent } from 'react'
import useSWR from 'swr'
import { createAgentJob, getUploadScopes, uploadFile } from '../services/api'
import { useAuth } from '../context/AuthContext'

function NewTask() {
  const { token } = useAuth()
  const [task, setTask] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [scope, setScope] = useState('')
  const [result, setResult] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const { data: scopeData } = useSWR(token ? ['upload-scopes', token] : null, ([, authToken]) => getUploadScopes(authToken))
  const scopes = scopeData?.scopes ?? []

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!token || !task.trim()) return
    setSubmitting(true); setError(null); setResult(null)
    try {
      for (const file of files) await uploadFile(file, scope || scopes[0] || 'private', token)
      const job = await createAgentJob(task.trim(), token)
      setResult(`Job ${job.job_id} is ${job.status}. View it in Tasks.`)
      setTask(''); setFiles([])
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
  </main>
}

export default NewTask
